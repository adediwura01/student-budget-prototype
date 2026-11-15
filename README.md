# FinSet

FinSet is a Student Budget & Expense Tracker project for university students. The frontend is a demo prototype; the Flask/PostgreSQL backend is being implemented in separately reviewed phases and is not feature-complete or production-ready.

## Project Structure

- `frontend/`: the React and Vite application, using JavaScript, plain CSS, and demo financial state rather than backend API data.
- `backend/`: Flask configuration, nine registered SQLAlchemy models, the reviewed initial migration, database-free tests, and dedicated PostgreSQL integration-test infrastructure. Application startup registers model metadata; it does not create tables or apply migrations. API endpoints and financial services are not implemented yet.
- `docs/`: schema design, model implementation notes, the PostgreSQL role contract, the integration report, and the two preserved original project documentation PDFs. Read the earlier PDF designs alongside the approved architecture decisions and phase-specific implementation notes.

## Required Software

- Node.js and npm compatible with `frontend/package-lock.json`; Node.js 24 is a suitable choice for the locked Vite and ESLint versions.
- Python 3.10 or newer with `venv` and pip, compatible with `backend/requirements.txt`; no workstation-specific interpreter location is required.
- PostgreSQL 18 for the reviewed migration and role contract. Installation paths, service names, administrative roles, and connection settings depend on each teammate's machine.
- Appropriate local PostgreSQL login roles. Database creation requires `CREATEDB` permission or administrator assistance; integration-role provisioning is a separate DBA operation, not application startup.

No database server, Docker, or WSL is installed by the project setup.

## Frontend Setup

Run commands from `frontend/`. On a fresh checkout, install exactly the locked dependencies:

```powershell
npm ci
```

Use the manifest and lockfile in `frontend/`, not a root-level dependency cache left from the earlier repository layout. No dependency upgrade is required for these setup instructions.

```powershell
npm run dev
npm run build
npm run lint
npm run preview
```

Development uses `http://localhost:5173`. Vite fails rather than silently choosing another port if 5173 is occupied.

## Backend Setup On Windows

Run commands from `backend/`. Create the virtual environment only if it does not already exist, then use its interpreter directly:

```powershell
if (-not (Test-Path -LiteralPath .venv)) { python -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

If `python` resolves to a Microsoft Store/Windows Apps alias, select an installed interpreter with the Windows Python launcher (`py -m venv .venv`) or invoke that interpreter by its own full path. Do not copy another workstation's interpreter path or recreate an existing environment without checking it first.

Activation is optional:

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, continue using `.\.venv\Scripts\python.exe` directly; changing system execution policy is unnecessary.

## Local Environment Variables

Use `backend/.env.example` as the template. Do not overwrite an existing `.env`:

```powershell
if (-not (Test-Path -LiteralPath .env)) { Copy-Item .env.example .env }
```

Set `SECRET_KEY` to a locally generated random value of at least 32 characters. A value can be generated with:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
```

Keep the secret in the ignored `.env`, never in `.env.example`, source code, or a frontend `VITE_` variable. Replace the template database role/password placeholders with your own local credentials; URL-encode special characters in credentials.

Dedicated integration credentials belong in the separate ignored `backend/.env.integration`, not the ordinary application `.env`. Never commit, print, or expose connection credentials. The integration runner must not fall back to development, test, production, or ordinary runtime credentials.

| Variable | Purpose |
| --- | --- |
| `APP_ENV` | `development`, `testing`, or `production` |
| `SECRET_KEY` | Required generated Flask secret |
| `DEV_DATABASE_URL` | `postgresql+psycopg` URL ending in `/finset_dev` |
| `TEST_DATABASE_URL` | Separate `postgresql+psycopg` URL ending in `/finset_test` |
| `FLASK_APP` | `app` |
| `FLASK_RUN_HOST` | Local default: `127.0.0.1` |
| `FLASK_RUN_PORT` | Local default: `5000` |
| `EMAIL_MODE` | Must remain `fake`; no email transport is implemented |

Local `.env` values are loaded with python-dotenv; process environment variables take precedence. Testing never falls back to the development URL. Development and testing require their respective database names on a local host and reject connection options that could override the target database. The default database connection timeout is 15 seconds.

Production requires `SECRET_KEY` and a separate `DATABASE_URL` in the process environment, without falling back to local development settings. Set `FLASK_SKIP_DOTENV=1` in production to disable the Flask CLI's own automatic dotenv loading. Production configuration support does not make this scaffold production-ready, and the Flask development server must not be used for production.

## PostgreSQL Preparation

**Isolation rule:** the following commands are for development/test setup only, not the isolated integration milestone. `finset_dev` and `finset_test` are strictly off-limits during integration work; its sole target is `finset_integration`.

Development and testing must use separate local databases, `finset_dev` and `finset_test`. Teammates need their own local setup. The verified integration migration does not imply that a schema has been applied to either of these databases.

Use PostgreSQL tools from your own installation's `bin` directory, either on `PATH` or through their full executable paths. The example below uses the application's default local endpoint; adjust the host/port for your approved development setup and supply an existing administrative role on your machine:

```powershell
$pgHost = "127.0.0.1"
$pgPort = 5432
$pgAdminRole = Read-Host "Existing local PostgreSQL administrative role"
pg_isready -h $pgHost -p $pgPort
psql -h $pgHost -p $pgPort -U $pgAdminRole -d postgres -c "SELECT datname FROM pg_database WHERE datname IN ('finset_dev', 'finset_test');"
```

Only create a database if the preceding check shows it is missing; do not drop or recreate an existing database:

```powershell
createdb -h $pgHost -p $pgPort -U $pgAdminRole -T template0 finset_dev
createdb -h $pgHost -p $pgPort -U $pgAdminRole -T template0 finset_test
```

Use your own configured authentication and password prompt. Do not assume password-free access, weaken authentication to match another workstation, or reuse an administrative development role as an application runtime or production identity.

Model registration still creates no application tables. The Phase 1.4.1 milestone was model-only; the later reviewed migration was applied separately to `finset_integration`. Do not reinitialize the existing migration repository with `flask db init`, regenerate the frozen revision with `flask db migrate`, or use `db.create_all()` as a shortcut. Further online migration operations require separate approval for their exact target.

## Run Both Development Servers

In a backend terminal, from `backend/`:

```powershell
.\.venv\Scripts\python.exe -m flask --app app run
```

In a separate frontend terminal, from `frontend/`:

```powershell
npm run dev
```

With the template defaults, Flask listens on `http://127.0.0.1:5000`. Vite's development proxy targets that address and forwards `/api/...` without stripping `/api`. The proxy is development-only; no production API URL is embedded in frontend source.

There are no API endpoints yet. A request to an unimplemented `/api/...` path should receive Flask's 404 through the proxy, not fabricated API data.

## Backend Tests

From `backend/`, use the database-free suite unless a separate live-test target has been explicitly approved:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -m "not integration" -p no:cacheprovider
```

The database-free suite covers configuration, model metadata, mapper configuration, offline PostgreSQL migration output, and integration-safety policy checks. Non-integration tests block database connections. Earlier offline results do not verify live PostgreSQL enforcement, and the presence of new tests does not mean they have passed.

The remediated integration harness also has its own database-free unit runner:

```powershell
.\.venv\Scripts\python.exe -B -m tests.integration_finset.unit -q
```

The [coverage and execution record](backend/tests/integration_finset/COVERAGE.md) reports completed Stage B database-free validation: **404 tests and 45 subtests passed**, no warnings, and zero real database, credential-file, live-readiness, or network attempts. These are recorded unit/harness results, not PostgreSQL integration totals or results rerun for this README correction.

The dedicated live suite exists in `backend/tests/integration_finset/`, but the remediated live domain suite has not been collected or executed and live readiness has not run. The legacy integration probe in `tests/test_config.py` targets `finset_test` and remains prohibited during isolated integration work. Generic/legacy integration selection is blocked; plain `pytest` or a broad integration-marker selection is not the dedicated live entry point.

## Isolated PostgreSQL Integration: Phase 1.4.3

**Recorded status: provisioning completed; migration `0001` successfully applied and verified in `finset_integration`.** The initial inspection stopped at a loopback `trust` authentication safety gate, but subsequent approved work established the dedicated integration database, approved roles/login principals, and integration-specific SCRAM authentication. The original stop is historical, not the current project status. See [the integration report](docs/postgresql-integration-test-report.md).

The approved [four-role contract](docs/postgresql-role-contract.md) separates the non-login groups `finset_runtime`, `finset_migrator`, `finset_owner`, and `finset_maintenance` from the dedicated integration login principals. Role provisioning is external to the [initial migration](backend/migrations/versions/0001_initial_finset_schema.py), which defines the nine application tables, migration-only guards, maintenance view, and object grants. Neither the provisioned baseline nor the applied revision makes Flask runtime credentials administrative.

Online Alembic uses only the process-environment `FINSET_MIGRATION_DATABASE_URL`, with explicit `finset_owner` assumption and no application-runtime URL fallback. Its role-contract checks are not the dedicated runner's database/endpoint guard; every future migration still needs independent approval of its exact target.

The dedicated live runner reads three separate settings from the ignored `backend/.env.integration`, not from `backend/.env.example` or ambient application configuration:

| Dedicated runner setting | Required login principal |
| --- | --- |
| `FINSET_INTEGRATION_RUNTIME_DATABASE_URL` | `finset_integration_runtime_login` |
| `FINSET_INTEGRATION_MIGRATION_DATABASE_URL` | `finset_integration_migrator_login` |
| `FINSET_INTEGRATION_MAINTENANCE_DATABASE_URL` | `finset_integration_maintenance_login` |

Its current policy pins `finset_integration` at `127.0.0.1:5432`, requires distinct passwords and exact login identities, and rejects URL overrides or credential fallback. This is an intentional test-target restriction, not a universal PostgreSQL installation layout. The guarded live connector also requires both runtime and compiled-wrapper libpq 17+ cancellation support; database-free tests do not verify native cancellation.

Phase 1.4.3.1 Stage A has a dedicated launcher, opt-in/target guards, connection/readiness helpers, and rollback-only live test source. Stage B database-free remediation validation is recorded, but live collection, readiness, execution, and acceptance remain outstanding. The source and unit results do not prove that live privilege, trigger, lifecycle, or concurrency tests pass.

Any later live run needs separate explicit approval and the controlled opt-in path. It must use only `finset_integration`, reject any other target before connecting, verify the actual database identity, and use only the dedicated credentials. Consult the suite's target-pinned policy rather than redirecting it to another database. An unexpected connection or authorization failure is a failure, not permission to skip a required test, weaken authentication, or broaden grants.

Retain the dedicated integration database and roles. No further server/role changes, database resets, downgrade, or re-upgrade are authorized by these setup notes. Downgrade is destructive and requires separate operator approval and backup planning. `finset_dev` and `finset_test` remain protected.

## Current Status

The nine approved models and Phase 1.4.2 migration are present, with earlier database-free verification recorded. Subsequent integration provisioning and the successful, verified application of revision `0001` are complete for `finset_integration` only. Remediated integration-harness unit validation passed 404 tests and 45 subtests; the live domain suite has not been collected or executed, and live readiness has not run.

Phase 1.4.3 live acceptance is not complete: live privilege/ownership checks, trigger behavior, plan and deletion lifecycles, concurrency and aggregate-limit protocols, downgrade, and re-upgrade results remain unverified. One rollback-only email-uniqueness race is implemented but unverified; committed shared-parent races remain deferred. Migration application and database-free checks are not substitutes for live acceptance. Backend API endpoints, authentication, financial calculations/caps, and recording/recovery services are still outstanding; the frontend remains a demo rather than a live backend client.
