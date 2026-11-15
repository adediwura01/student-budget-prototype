# Phase 1.4.3 PostgreSQL Integration Test Report

**Recorded status: integration provisioning completed; migration revision `0001` successfully applied and verified in `finset_integration`. Live integration acceptance remains incomplete.**

Documentation corrected on 2026-11-15 against the repository and recorded follow-up project state. No PostgreSQL connection, migration, role change, or test execution was performed for this documentation correction. The original blocked inspection below is retained as history, not as the current provisioning status.

## Original Read-Only Inspection (Historical)

These observations describe the initial inspection on one Windows workstation. Its installation path, service name, administrator, and endpoint are not universal teammate setup requirements.

| Item | Observed result |
| --- | --- |
| PostgreSQL version | 18.6, reported by the running server |
| Installation | `C:\Program Files\PostgreSQL\18` |
| Windows service | `postgresql-x64-18`, running |
| Inspected endpoint | `127.0.0.1:5432` |
| Administration database | `postgres` only |
| Inspection identity | Existing `postgres` administrator; inspection only, not a test identity |
| Requested integration database | `finset_integration`; absent at this initial inspection, subsequently provisioned |
| Protected databases | No connection to, content inspection of, or modification of `finset_dev` or `finset_test` |

At that initial inspection, two read-only administration sessions issued five explicit SELECT statements to verify identity and inspect database-name, role-name, and authentication-rule metadata. The connection specified the maintenance database and loopback endpoint, disabled password-file lookup, cleared inherited `PG*` connection variables for the process, and did not load development/test connection strings or passwords. No password was supplied or printed. Authentication-rule options were not printed.

## Initial Database and Role Collision Checks

None of the following existed during the original pre-provisioning checks:

- `finset_integration`
- `finset_runtime`
- `finset_migrator`
- `finset_owner`
- `finset_maintenance`
- `finset_integration_runtime_login`
- `finset_integration_migrator_login`
- `finset_integration_maintenance_login`

The final three names were candidate disposable login identities at that time. Subsequent approved provisioning established the dedicated database, four non-login groups, and integration login principals. The historical absence checks must not be interpreted as their current state or as a live privilege-test result.

## Original Authentication Safety Gate

The original inspection reported these applicable loopback authentication rules:

```text
host  all  all  127.0.0.1/32  trust
host  all  all  ::1/128       trust
```

Local socket rules also used `trust` in that inspection. Under this policy, a local client can claim a login role without proving knowledge of that role's password. This was consistent with the successful password-free administrator inspection.

Under those original `trust` rules, merely creating different login names and assigning passwords would not, by itself, have proven the approved credential separation: a client could instead claim a privileged migration or administrator login. Tests limited to the privileges of an already-selected runtime session would have missed that authentication bypass.

That inspection therefore stopped before provisioning and changed no server configuration, authentication rules, databases, or roles. Subsequent separately approved work established integration-specific SCRAM authentication for the dedicated login principals. The initial blocker is no longer the recorded status of the integration setup; this does not certify the entire cluster's authentication or establish passing live authorization tests.

## Verified Follow-Up Baseline

The recorded follow-up project state confirms:

- The dedicated `finset_integration` database and approved role/login setup were established.
- Dedicated integration SCRAM authentication was provisioned after the original inspection.
- The reviewed initial migration, revision `0001`, was successfully applied to `finset_integration`, and its application was verified.

The [four-role contract](postgresql-role-contract.md) remains authoritative. The four group roles are non-login permission identities; actual runtime, migrator, and maintenance logins are separate. Role creation is a DBA operation, not part of [migration `0001`](../backend/migrations/versions/0001_initial_finset_schema.py). Online Alembic uses only the process-environment `FINSET_MIGRATION_DATABASE_URL` and explicit `finset_owner` assumption, with no application-runtime credential fallback. Its role checks do not independently pin the integration database/endpoint.

The repository contains the reviewed initial migration and nine model declarations. It also contains Phase 1.4.3.1 Stage A infrastructure under `backend/tests/integration_finset/`: the controlled launcher, opt-in/target policy, guarded connections, readiness checks, rollback-only live test source, and [coverage notes](../backend/tests/integration_finset/COVERAGE.md). The remediated live domain suite has not been executed or collected and live readiness has not run. Source presence is not a passing live test result.

Separately, the coverage notes record completed **Stage B database-free remediation validation: 404 tests and 45 subtests passed**, with no warnings and zero real database, credential-file, live-readiness, or network canary attempts. The recorded command, from `backend/`, was:

```powershell
.\.venv\Scripts\python.exe -B -m tests.integration_finset.unit -q
```

This fixed-path unit runner uses fakes, synthetic inputs, read-only migration bytes, and non-database subprocess probes. Its totals are not PostgreSQL integration totals. Native cancellation, catalog attestation, live DML, and server-side rollback/receipt behavior remain unverified; terminating a test subprocess is not proof that PostgreSQL completed rollback.

The live-database baseline is limited to provisioning and verified migration application. It does not assert that all live privileges, trigger behavior, plan/deletion lifecycles, concurrency protocols, or migration round trips have passed. No application schema state is inferred for the protected `finset_dev` or `finset_test` databases.

## Current Verification Status

| Area | Result |
| --- | --- |
| PostgreSQL service and maintenance connection | Passed during the original read-only inspection |
| Initial database/role-name collision checks | Passed at the original inspection: requested names were then absent |
| Integration database and approved role/login provisioning | Completed in subsequent approved work |
| Dedicated integration SCRAM authentication | Established in the recorded follow-up setup; not a blanket cluster-security or privilege-test claim |
| Initial migration upgrade (`0001`) | Successfully applied to `finset_integration` and verified |
| Earlier configuration/model/offline migration checks | Recorded database-free verification; not live enforcement evidence |
| Stage B database-free remediation validation | 404 tests and 45 subtests passed; no warnings; zero real-resource canary attempts |
| Explicit integration-test opt-in/identity guards and Stage A suite | Source and unit checks exist; live collection/readiness/execution results outstanding |
| Live role, ownership, grant, and function privilege acceptance | Unverified; no passing live-suite result claimed |
| Constraint and trigger behavioral tests | Unverified; migration application is not behavioral acceptance |
| Plan recording/undo/reconfirmation lifecycle tests | Unverified |
| Account/transaction deletion lifecycle tests | Unverified |
| Rollback-only email-uniqueness concurrency case | Implemented source, but unverified on PostgreSQL |
| Committed shared-parent plan/category/token races | Deferred; no passing concurrency result claimed |
| Aggregate-limit protocols | Unverified; application caps/services are not implemented by this schema or suite |
| Downgrade and re-upgrade | Unverified; separate destructive-operation approval required |
| Remediated Stage A live domain suite and readiness | No live execution/collection result recorded; readiness has not run |

The earlier statement that migration execution was never reached is superseded by the verified `0001` application. No offline result, source review, or successful upgrade is presented as a substitute for the outstanding live acceptance tests. No unexecuted test is reported as passing or silently skipped.

## Outstanding Work and Safety Rules

Review the Stage A coverage and safety boundaries before any separately approved collection, readiness run, or live execution. The dedicated suite is target-pinned; it is not permission to connect to arbitrary local databases. Complete and record the outstanding privilege, trigger, lifecycle, and concurrency coverage before claiming Phase 1.4.3 acceptance.

The current runner pins `finset_integration` at `127.0.0.1:5432` and the exact `finset_integration_runtime_login`, `finset_integration_migrator_login`, and `finset_integration_maintenance_login` principals. It accepts only the three literal `FINSET_INTEGRATION_RUNTIME_DATABASE_URL`, `FINSET_INTEGRATION_MIGRATION_DATABASE_URL`, and `FINSET_INTEGRATION_MAINTENANCE_DATABASE_URL` settings in the dedicated credential file, with distinct passwords and no URL override or environment fallback. This policy is an approved test-target constraint, not a required installation path or generic database runner.

Stage A permits rollback-only tests, not migrations, DDL, reset, committed fixtures, or deletion of leftovers. Committed concurrency cases need their own reviewed execution/cleanup design. The coverage notes also retain an unresolved token-consumption timestamp mutability concern; the existing guards and permission denials must not be described as proof that every lifecycle or immutable-trigger branch is covered.

Do not repeat provisioning, reset the retained integration database, broaden role grants, or change server authentication to make a test pass. Downgrade and re-upgrade remain separate work requiring explicit operator approval and backup planning. The dedicated integration database and roles must be retained.

Before any later live test, require explicit approval, the controlled opt-in path, and dedicated integration URLs; reject every database name except `finset_integration` before connecting and verify the actual database identity immediately after connection. Never fall back to `DEV_DATABASE_URL`, `TEST_DATABASE_URL`, a production or ordinary runtime URL, or the legacy `finset_test` connectivity probe. Unexpected connection/authorization failures are failures, not grounds to skip required tests or loosen isolation.

Keep integration credentials only in the ignored `backend/.env.integration`, never in this report, committed files, or frontend variables. `finset_dev` and `finset_test` remain off-limits during integration work.

## Documentation Change Boundary

- The original inspection created this report and recorded the then-blocked status in the root README.
- This correction updates only `README.md` and `docs/postgresql-integration-test-report.md` to reflect the verified follow-up baseline and outstanding tests.
- No application source, frontend file, migration, database file, role contract, schema design, dependency, original PDF, or `.gitignore` was changed by this correction.
- No database connection, migration execution, role change, credential access/change, or test execution was performed for this correction. The provisioning and upgrade results above are recorded prior work, not operations repeated here.
- The protected development/test databases were not accessed, and no credentials were printed or exposed.
- No Git staging, commit, push, history, or remote changes were performed for this correction.

Phase 1.4.3 is not complete. Provisioning and verified migration `0001` application are recorded as completed; live acceptance, downgrade, and re-upgrade remain outstanding.
