# Phase 1.4.1 Model Declaration Coverage

The authority remains [database-schema-design.md](database-schema-design.md). Its O1-O10 decisions are unchanged.

## Declared In Python

The nine models live in `backend/app/models/`, one file per entity, and are exported by the package initializer. Importing the Flask application imports that package before Flask-Migrate inspects `db.metadata`. This registers metadata only; it does not connect to PostgreSQL, create tables, or run migrations.

Declarations include the approved column names, types, nullability, server defaults, named primary/unique/foreign keys, and row-local checks. UUIDs use `gen_random_uuid()` server defaults; timestamps use timezone-aware types; all money uses positive `BigInteger` kobo values. No configurable money cap is duplicated as a database check.

PostgreSQL-supported partial/expression indexes and the alert index's `NULLS NOT DISTINCT` option are represented with SQLAlchemy `Index` declarations. They can be compiled without a database, but do not exist in PostgreSQL until an approved migration creates them. Review future generated migrations explicitly for these index details.

## Relationship Safety

All ORM relationships are read-only navigation (`viewonly=True`) with no persistence cascades. Private composite joins include the approved owner, parent, and type columns. This deliberately avoids relationship assignments that silently write another object's owner into a new record or null/delete financial children during parent deletion.

Future services must assign authenticated scalar foreign keys deliberately. Appending to a relationship collection is not an insert/update API. Relationships include retained deleted/archived rows; financial queries must apply the approved active-record filters explicitly. In particular, `Plan.transaction` includes a retained deleted result so it cannot be mistaken for an available slot.

The credential foreign keys declare database `ON DELETE CASCADE`; financial references declare `RESTRICT`. Read-only ORM navigation does not replace these database actions or backend authorization.

## Required Migration-Only Objects

The following approved rules cannot be faithfully implemented as ordinary column/relationship declarations. No Python event hook, fake constraint, automatic DDL, trigger, or function substitutes for them in this milestone.

| Deferred object | Required behavior |
| --- | --- |
| Shared-category reference guard | Validate the actual category's ownership/type for transactions, plans, and budgets; distinguish system NULL ownership from another user's custom category; lock appropriately against archival and preserve legitimate historical references. |
| System-category and immutable-binding guards | Protect system category writes through the approved role boundary. Prevent changes to identities, owners, plan type/link, budget identity, limit kind, event snapshots, and credential bindings/absolute expiry. Preserve one-way revocation/consumption/resolution and nondecreasing security/activity values. |
| Plan result-generation allocator | On an authorized linked transaction insert, validate the owned pending plan and reserved slot, allocate generation 1 or the single generation-2 replacement, and roll back the counter if insertion fails. Undo/purge must not reset it. The model currently declares only the 0-2 range and initial 0. |
| Deferred plan/result state check | At transaction end, re-read affected final rows: completed means exactly one active result; pending/cancelled means none active; generation 0 has no result. Support legitimate parent/result removal together without relying on queued intermediate values. |
| Database role permissions | Configure application versus maintenance permissions so runtime callers cannot bypass system-category guards or disable integrity objects. No roles or grants were changed here. |

The unfiltered `UNIQUE(transactions.plan_id)` is declared now, but it is not a substitute for the generation allocator or deferred state check. Likewise, a category existence FK is not yet the shared-category ownership/type guard. Full enforcement must not be claimed before those migrations and PostgreSQL integration tests are approved and completed.

## Later Service Responsibilities

These are deliberately not implemented in model constructors, setters, or lifecycle methods:

- Authentication, password handling, token issuance/redemption, and user-initiated live-account deletion.
- The central entry cap and all five aggregate caps, including lowered-cap handling and early per-user locking.
- Explicit plan recording/undo/reconfirmation, version advancement, and actual-amount/date validation.
- Current/past/future budget permissions, archival, parent-month containment, and locked overlap checks.
- Future-date rejection using Africa/Lagos, actual balance/report calculations, and alert generation.
- Recovery/expiry timing, UTC value handling, and explicit `updated_at` maintenance. A server default applies only at insertion; no automatic update/version behavior is added here.

This list is the existing schema's separation of responsibilities, not a change to the approved rules or permission to implement them now.

## Database-Free Verification

From `backend/`, run:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -m "not integration" -p no:cacheprovider
```

Non-integration tests block SQLAlchemy engine and psycopg connections. Model tests compare column metadata with the approved document, configure mappers with SQLAlchemy warnings treated as errors, inspect keys/relationships/indexes, and compile PostgreSQL table/index definitions into strings only. They do not execute those definitions or simulate database enforcement with SQLite.

The existing `integration` test is excluded in this milestone. Actual constraint enforcement, concurrency, and migration round trips must be tested against PostgreSQL only after separate approval. No database contents were inspected or changed for model verification.
