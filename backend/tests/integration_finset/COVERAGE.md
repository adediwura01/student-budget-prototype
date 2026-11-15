# FinSet Coverage

## Status

The eight recovery findings are remediated in test-only infrastructure. Stage B
DB-free validation completed: **404 tests and 45 subtests passed**, with no
warnings. The live domain suite has **NOT been executed or collected** and live
readiness has not run. All validation used fixed unit-test paths, fakes, synthetic
privileges/output, read-only migration bytes, or non-database owned subprocesses.
The preloaded Stage B canary reported zero real database, credential-file,
live-readiness, or network attempts. No production/dependency/Git changes or
database operations were made. Earlier live migration audits do not establish
that this remediated suite works against PostgreSQL.

From `backend/`, the completed Stage B command was:

```text
.\.venv\Scripts\python.exe -B -m tests.integration_finset.unit -q
```

This runner fixes collection to `unit/` plus the existing unmarked
`tests/test_integration_safety.py`, rejects integration markers, disables plugin
autoload/cache/bytecode output, and denies real connectors/readiness/secret-file
reads before test imports. Probe children also install that deny-all canary.

## Future Review

From `backend/`, only after the relevant execution or collection approval:

```text
python -B -m tests.integration_finset --run-finset-integration
python -B -m tests.integration_finset --run-finset-integration --collect-only
```

The first command defaults to rollback-only execution; the second is for a future
approved collection review. Neither command was run for these changes. The
controlled launcher fixes the suite/configuration, explicitly loads its safety
plugin, and disables third-party plugin autoload. Ambient `PYTEST_ADDOPTS` and
`PYTEST_PLUGINS`, unsafe reporting, configuration, plugin, path, and worker
overrides are rejected. Arbitrary `pytest -m integration` is not a supported
route: the existing legacy test targets `finset_test` and is excluded.

Public sync/async psycopg and SQLAlchemy connection entry points are blocked
when the root test conftest is imported, before test collection or higher-scope
fixture setup. The controlled launcher captures its one trusted connector first.
Selector syntax and marker names are checked before pytest can echo invalid
input. Collection/failure output is redacted without changing skipped-report
tuples, and expected-failure reasons are redacted separately. An aborted teardown
retains authorization while pytest still has pending fixture finalizers. The
outer session-finish wrapper clears execution authority, not the output filter;
the worker releases its cache after pytest/unconfigure finishes and the parent
retains its filter until every captured descriptor has drained.

Selection must be nonempty, entirely under `tests/integration_finset`, and carry
both `integration` and `finset_integration`. Test parameters may not shadow the
protected connection/fixture names; domain helper selectors use `builder`.
Long launcher options must be supplied in full. `--allow-finset-commits` is deliberately
rejected in Stage A, even for a rollback-only selection; it is not a bypass.

## Remediation Validation

| DB-free file | Passed | Scope |
| --- | ---: | --- |
| `../test_integration_safety.py` | 229 | Existing target, credential-format, selection, receipt and redaction regressions |
| `unit/test_privileges.py` | 30 | Legitimate defaults, PUBLIC increases, hidden catalogs, effective CREATE and fake catalog queries |
| `unit/test_lifecycle.py` | 25 | Runtime/build cancel capability, positive shared budgets, case verification ownership, interrupted joins, late opens, failed role reset/rollback |
| `unit/test_output.py` | 5 | Raw, encoded, JSON, repr and connection-token redaction; bounded atomic registry |
| `unit/test_safety_hooks.py` | 7 | Private registration, collection denial, warning/source sanitization, interrupted teardown and output-cache lifetime |
| `unit/test_selectors.py` | 65 | Complete Boolean marker grammar and compile-only older-parser compatibility |
| `unit/test_fingerprint.py` | 26 | LF/CRLF equivalence, all other bytes preserved, unchanged pin and pre-AST rejection |
| `unit/test_supervisor.py` | 17 | Fake deadlines/handshakes and real non-database emit/hang/malformed/oversize child probes |

The 45 additional unittest subtests exercise supervisor/output variants. These
are not PostgreSQL integration totals. Fake gates prove routing and policy, not
native database cancellation or DML behavior.

## Source Coverage

| Area | Implementation and validation boundary |
| --- | --- |
| DB-free safety | `../test_integration_safety.py` imports only `policy` and `scope` from the project. It has no integration marker, so the normal database blocker remains active. No real credentials loader is called. |
| Targets and credentials | Synthetic URLs only in unit tests; explicit non-secret parameter IDs; dedicated database/host/port/login checks; missing fields/passwords; query, service, multi-host and control-character rejection; redacted representations/errors; three literal credential settings with duplicate/missing-key and environment-fallback rejection. Raw controls are rejected before URL parsing; decoded controls and malformed percent escapes are also rejected. |
| Invocation and scope | Explicit opt-in; legacy/mixed/outside/empty selections; both markers; protected-fixture parameter names; committed-marker/allow-flag rejection; unsafe reporting/config/plugin/worker flags; sanitized selectors and report contracts; registered UUID receipts, ownership/role/table rebinding, foreign scopes, duplicate IDs and broad selectors. Valid allowlists preserve exact receipt order without mutation. |
| Domain DML | Implemented source covers runtime CRUD, required values/enums, normalized-email uniqueness, owned references, category-reference rules and restricted parent deletion. Financial/auth source covers integer money, budget/limit periods, alert deduplication, session/token row shape and lifecycle checks. All remain unverified. |
| Plans and privileges | Result allocation, explicit completion, deferred invalid final states, statement/savepoint rollback, retained-result uniqueness, undo/restoration, two-generation exhaustion, scoped purge/deletion, category archival, restricted view CRUD, allocator/counter denial, and explicit read-only migrator owner assumption/reset. ACL rejection is not claimed as execution of an unreachable immutable-trigger branch. |
| Readiness | Exact application ACLs/roles and a conservative PostgreSQL 18 platform-privilege baseline, not a universal server-integrity audit. No live readiness ran. The source pin normalizes only CRLF to LF in memory; migration bytes and the reviewed digest are unchanged. |
| Rollback isolation | An exact-ID receipt registry limits reads/updates/deletes to synthetic rows. Ordinary tests and negative savepoints always roll back; rejection contexts force deferred constraints before their savepoint is rolled back and revalidate the restored baseline. Separate read-only connections check INSERT receipts are absent after rollback, without deleting leftovers. |

## Concurrency

One rollback-only, two-connection `users.email` uniqueness race is included in
the implementation scope: A inserts an uncommitted synthetic user; B attempts
the same email and blocks; A rolls back; B succeeds and then rolls back. Both
connections roll back, with no commit or durable shared parent. This case is
unverified, not deferred. All shared-parent plan/category/token races requiring
commits remain deferred.

Setup/observation share a deadline; the blocker has bounded teardown grace.
Worker objects are tracked before startup, including uncertain interrupted starts.
Joins, cancellation and closure consume shared cooperative deadlines; cancellation
requires BOTH runtime and compiled-wrapper libpq 17+ support before credentials
load. Legacy unbounded cancellation is prohibited. Verification/observer handles
retain case ownership, and abort rejects late opens for that case.
Connected handles are registered before identity inquiries, late opens are
rejected once teardown begins, and registry entries remain until closure. Busy
connections are not closed concurrently with driver operations; failure to drain
or close them aborts the run without a cleanup/recovery attempt. A retired owner
context clears its Python flag even when RESET ROLE or savepoint rollback fails;
no further session operation is allowed after an uncertain role context.

The launcher owns one child process and captures OS stdout/stderr, including
pytest warning/internal-error/interruption and capture-manager flush paths.
Only the private control pipe carries secret registration; acknowledgement is
required before credentials can be used. No credential CLI/environment/log/file
transport is introduced. Captured output is bounded and withheld until complete,
then filtered with raw/encoded/JSON/repr variants. Malformed control, timeout,
overflow or filtering failure suppresses output and marks the run unverified.
The parent delays Ctrl+C only through bounded child kill/reap/drain and restores
its original handler. It never kills PostgreSQL or an unrelated process.

Default hard-stop budget is 120 seconds plus 5 seconds for owned-process cleanup,
subject to healthy OS process/pipe/termination operations. Native rollback/close
latency cannot be proved by Python thread timeouts; subprocess termination is
the outside boundary and does not itself prove server-side rollback completed.

## Platform Baseline

`privileges.py` derives the policy from PostgreSQL 18 `postgres.bki`,
`system_views.sql`, `system_functions.sql`, and `information_schema.sql`, not
observed grants. Legitimate PUBLIC schema USAGE, ordinary builtin EXECUTE/type
USAGE, metadata SELECT, SQL/PLpgSQL USAGE and `pg_settings` SELECT/UPDATE are
allowed explicitly. Hidden information-schema helper SELECT, sensitive catalog
access, restricted function EXECUTE, grant options, configuration privileges,
and persistent non-application schema CREATE fail closed. Normal helper composite
and array-type USAGE and implicit application TOAST ownership are distinguished
from extra grants. Unknown privileged objects require baseline review, not repair.

## Boundaries

- No DDL, migrations, database/schema reset, fixture journal, committed fixtures,
  or committed-data cleanup is part of Stage A.
- There is no data-deletion cleanup routine. Teardown uses rollback and scoped
  receipt checks, not automatic deletion of leftovers. `validate_cleanup_scope`
  is a pure, no-I/O allowlist validator, not a cleanup executor. Domain `DELETE`
  cases target registered receipts and test domain/FK behavior. No cascade user
  deletion is used.
- Live DML tests exercise the existing schema without expanding source policy.
  The shared runtime role has no per-student RLS; owned-reference checks do not
  establish student-level SQL isolation.
- NGN 10 million / 1 billion caps are absent from database constraints. Input
  precision, TTL enforcement, redemption workflows and optimistic-version
  policies are deferred application concerns, not promises of this DB suite.
- Direct immutable-trigger branches and `ON CONFLICT` skipped-ID cases requiring
  owner writes are not covered. Runtime permission denials do not prove those
  trigger branches.

## Open Concerns

- Separate unresolved database concern: changing one non-NULL token-consumption
  timestamp (`auth_tokens.consumed_at`) to another non-NULL value. Preventing it
  from being cleared does not settle this mutability question or implement
  redemption policy.
- The raw URL-control validation and DB-free regression tests passed Stage B.
- Readiness and pytest hook behavior require separately approved execution to
  establish that they work with the installed PostgreSQL/pytest versions.
- Selector validation needs only `Expression.compile`, not the newer `idents`
  API. The profile intentionally supports bare Boolean expressions over four
  approved markers, not marker-call arguments. A fake older parser passed;
  no older dependency was installed or executed.
- Native cancellation, PostgreSQL catalog attestation, rollback receipts and
  server responsiveness still need separately approved live validation. The
  very short hard-stop probe may terminate during startup; it is not evidence
  of PostgreSQL cancellation latency.
- The facade and private readiness connector are trusted test-harness code, not
  a sandbox for arbitrary hostile Python. No general SQL/commit API is exposed
  to domain tests. Committed or cross-role shared-fixture cases need their own
  reviewed execution and cleanup design in a later stage.
