# FinSet PostgreSQL Role Contract

This is the approved authorization contract for the prepared Phase 1.4.2 migration. No role, grant, schema, table, view, function, or trigger has been applied to either database by this milestone.

The authoritative financial design remains [database-schema-design.md](database-schema-design.md). PostgreSQL roles are connection/permission identities, not rows in FinSet's `users` table.

## Four Non-Login Group Roles

| Role | Responsibility and boundary |
| --- | --- |
| `finset_runtime` | Ordinary Flask data operations only. Must not own application schemas, tables, views, or privileged functions, and must not be a member of owner, migrator, or maintenance. |
| `finset_migrator` | Controlled schema migration identity. Can explicitly assume `finset_owner`, but does not automatically inherit owner or maintenance privileges in an ordinary session. Migration credentials are separate from runtime credentials. |
| `finset_owner` | Non-login owner of application objects. Never the Flask runtime identity. Its broad DDL authority is trusted administrative capability, not a privilege granted to the application. |
| `finset_maintenance` | Restricted system-category maintenance only. Must not own the application schema/general tables or be a member of runtime, migrator, or owner. |

All four groups are non-login and non-superuser, without database/role creation, replication, or RLS-bypass capabilities. Actual login principals and credentials are provisioned separately by the DBA with only the appropriate memberships. Runtime/maintenance logins must not gain administrative capabilities through another membership or independent grant.

## External Provisioning Required Before Application

The DBA, not the migration, creates/removes the four roles and login principals. The migration contains no `CREATE ROLE`, `ALTER ROLE`, `DROP ROLE`, or role-membership grants.

For PostgreSQL 18, provision the migrator-to-owner edge with **SET allowed, INHERIT disallowed, and no ADMIN option**. The membership form is:

```sql
-- DBA provisioning reference only; not executed by the migration.
GRANT finset_owner TO finset_migrator
    WITH INHERIT FALSE, SET TRUE, ADMIN FALSE;
```

The migration login must have a SET-capable membership path through `finset_migrator` to `finset_owner`, but no automatic owner or maintenance privileges and no runtime membership. Setting a role's default inheritance attribute is not a substitute for checking PostgreSQL's membership-level INHERIT/SET options.

Runtime and maintenance login principals may inherit their own group's limited permissions or explicitly assume that group. The migration never supplies passwords or connects using a non-login group name.

In each dedicated FinSet database, the DBA must also prepare the existing `public` application schema:

- `finset_owner` owns `public`; model table names continue to resolve in the existing default application schema.
- Runtime and maintenance have schema USAGE, not CREATE or ownership. An ordinary migrator session has no CREATE there until explicitly assuming owner.
- PUBLIC must not have CREATE in this schema. Preflight inspects its schema ACL explicitly, including the default ACL when `nspacl` is NULL, and rejects CREATE without changing grants. The separate runtime, maintenance, and migrator checks remain in place.
- Unqualified application model names must resolve to the trusted `public` schema, not a login-owned shadow schema. The migration explicitly selects `public` after its protected preflight; the DBA must keep the runtime search path consistent with that application namespace.
- Database CONNECT is provisioned for the required login principals/groups. Do not add unrelated server-level privileges.
- Owner table defaults must remain owner-only, including for Alembic's version table. Function defaults may retain PostgreSQL's standard PUBLIC execution only until the migration explicitly revokes it on each new function. Other default grants are rejected, rather than silently exposing new objects or changing global defaults.

The preflight checks these requirements when a migration is eventually executed. It does not repair cluster roles or take ownership of a schema silently. A DBA must resolve a failing precondition before retrying. Existing development administrator credentials are not a substitute for the restricted migration/runtime identities.

## Explicit Migration Role Assumption

The Alembic environment uses `FINSET_MIGRATION_DATABASE_URL` for a future online run. It never falls back to the Flask runtime database URL. This process-only value contains the separately provisioned migration login; it does not belong in frontend variables or checked-in configuration.

Before Alembic creates even its version table, the environment validates the contract and explicitly executes `SET LOCAL ROLE finset_owner` inside the migration transaction. All application objects and the version table are therefore owned by `finset_owner`. Role assumption ends with the transaction; it is not an inheritance or cluster-role change.

Offline compilation does not require this URL or a database connection. It emits the same preflight/role-assumption SQL into a string rather than executing it.

## Runtime Data Permissions

Runtime receives SELECT and DELETE on the nine application tables. DELETE is required for authorized transaction retention cleanup and user-initiated live-account deletion; authenticated user scope, eligibility, and early locks remain mandatory service responsibilities.

INSERT and UPDATE use explicit column lists. Generated identity/creation fields are not ordinary write inputs. Immutable bindings cannot be updated. In particular, runtime receives **no direct INSERT or UPDATE permission on `plans.result_generation`**, no table-wide UPDATE grant that would bypass that restriction, and no TRIGGER, TRUNCATE, schema CREATE, or ownership privileges.

These grants do not establish the authenticated FinSet user. Composite FKs and category guards enforce referential ownership, while backend authorization must scope private data to the validated user's UUID. RLS is not silently introduced.

## Maintenance-Only Category View

Maintenance has no direct privileges on the nine base tables. Its interface is the owner-owned, automatically updatable `public.finset_system_categories` view:

- It exposes only rows whose `owner_user_id IS NULL` and only system-category columns.
- `security_barrier` and a CHECK OPTION preserve the row boundary.
- Maintenance can SELECT/DELETE visible system rows, INSERT their name/type, and UPDATE their name/archive/update-time fields.
- It cannot provide an owner, rewrite identities/types, read private custom categories through the view, or modify financial tables.
- Existing restrictive category FKs still block deleting referenced categories.

This view is an authorization interface, not a tenth application table or a new business feature. Runtime receives no privileges on it.

The view uses its owner's base-table permissions, but this does not turn the caller into the owner. The category mutation trigger is explicitly `SECURITY INVOKER` and uses PostgreSQL `current_user` with `pg_has_role(..., 'USAGE')` to authorize the effective maintenance/runtime identity. Caller data, custom session variables, and claimed user IDs are not maintenance credentials. Direct base-table DML remains subject to the trigger as well as grants.

## Trigger Function Security

Every FinSet trigger function explicitly declares its security mode, ownership by `finset_owner`, and the hardened `search_path` of `pg_catalog, pg_temp`. All application relations and relation-identity literals are explicitly `public`-qualified; no function needs `public` in its lookup path. PostgreSQL built-ins resolve from `pg_catalog`, with the temporary schema explicitly last. This includes the SECURITY DEFINER result allocator and all seven SECURITY INVOKER functions.

The migration session also uses the hardened path during preflight. Its existing post-preflight `public`-first path for application DDL is separate from the function-local setting and is selected only after the schema/role checks pass. Ownership, role membership rules, table grants, maintenance-view architecture, and function EXECUTE restrictions are unchanged.

All new function EXECUTE privileges are revoked from PUBLIC and the other three groups. They are trigger-only functions, not application-callable procedures. PostgreSQL checks trigger-function EXECUTE when the owner creates the trigger; ordinary DML still fires the installed trigger. Runtime cannot attach the privileged allocator to a table it controls because it has neither function EXECUTE nor application-table TRIGGER privileges.

Standard PostgreSQL built-ins remain platform facilities; the migration does not broadly revoke unrelated catalog-function privileges.

### Narrow result allocator

The result path has two parts:

1. An invoker BEFORE INSERT guard locks and validates the owned pending plan, available generation, and absence of any retained result.
2. An owner-owned **SECURITY DEFINER AFTER INSERT** allocator advances only that plan's generation. AFTER INSERT is deliberate: a skipped `ON CONFLICT DO NOTHING` row must not consume a generation. Failed statements roll back the inserted result and counter together.

The definer validates its trigger table/operation and the owned plan/result relation, and executes only fixed SQL for that counter. It does not modify amounts, plan status, versions, or unrelated rows. Runtime receives no owner membership or direct EXECUTE grant.

A plan generation guard rejects ordinary counter writes. A permitted increment must occur in the protected owner execution context of nested trigger execution, advance exactly one step, and remain within 0-2 while the plan is pending. Trigger depth is a nesting assertion, **not the authorization credential**: role isolation, column privileges, revoked EXECUTE, trusted function ownership, and the fixed definer body establish that boundary. An attacker-owned temporary trigger still runs as the attacker and cannot manufacture owner execution.

All other guards and the deferred final-state checker are SECURITY INVOKER. Category mutations are authorized independently from category-reference validation, so the counter allocator cannot accidentally become a maintenance-authorized category writer.

## Upgrade and Downgrade Boundaries

The initial revision freezes the nine-table definitions and all approved indexes instead of importing changing application model metadata. It creates the guards, the maintenance view, and explicit object grants only after the ordinary schema exists.

Downgrade is destructive to these application tables and requires separate operator approval and backup planning. It removes the maintenance view, dependent triggers, functions, indexes, and tables in dependency-safe order. It does not drop either database, the pre-provisioned `public` schema, or any role or role membership. Unexpected external dependencies cause failure rather than a broad CASCADE.

The approved schema and O1-O10 decisions are not changed. This work adds no authentication endpoints, recording service, financial calculation, or aggregate-cap implementation.

## Verification and Later Live Integration

Current verification is connection-blocked: model checks, recorded migration operations, PostgreSQL SQL compilation, and assertions about role checks, ownership, grants, view scope, and function/trigger definitions. Compiling PL/pgSQL text is not proof that PostgreSQL has parsed or executed it.

From `backend/`, the preparation-only verification command is:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -m "not integration" -p no:cacheprovider
```

The migration tests render both Alembic directions with `sql=True` into memory and forbid engine creation on that path. Do not run online upgrade/downgrade or the integration-marked test during this milestone.

A later explicitly approved PostgreSQL integration milestone must test:

- External provisioning and explicit owner assumption, including rejection of inappropriate memberships/default privileges.
- Runtime direct/shared-category attempts and maintenance view CRUD, with private/financial-table access denied to maintenance.
- Trigger-only allocator execution despite revoked direct EXECUTE; spoofed flags, caller parameters, direct counter writes, and attacker-controlled trigger nesting do not grant owner authority.
- Conflict/no-op inserts do not consume a generation, concurrent inserts do not duplicate results, and undo/purge never reset the counter.
- Deferred state validation reads final rows, including legitimate parent/result deletion.
- Nullable archive transitions, immutable fields, monotonic states, and update/downgrade behavior under the intended roles.

No live integration test, role provisioning, or migration application is authorized by this document.

## PostgreSQL References

- [Role privilege inquiry: MEMBER, USAGE, SET](https://www.postgresql.org/docs/18/functions-info.html#FUNCTIONS-INFO-ACCESS-TABLE)
- [Views, caller identity, check options, and updatability](https://www.postgresql.org/docs/18/sql-createview.html)
- [Trigger execution context, ordering, and conflict behavior](https://www.postgresql.org/docs/18/trigger-definition.html)
- [Trigger creation privileges](https://www.postgresql.org/docs/18/sql-createtrigger.html)
