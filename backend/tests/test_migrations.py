"""Inspect and render migrations only. No SQL is submitted to a database."""

import ast
import importlib.util
from io import StringIO
from pathlib import Path
import re

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import ops
import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex

from app.extensions import db


BACKEND = Path(__file__).resolve().parents[1]
MIGRATIONS = BACKEND / "migrations"
REVISION_FILE = MIGRATIONS / "versions" / "0001_initial_finset_schema.py"
DIALECT = postgresql.dialect(paramstyle="named")


def normalized(value):
    return " ".join(str(value).replace("public.", "").split())


@pytest.fixture
def revision():
    spec = importlib.util.spec_from_file_location("finset_initial_revision_test", REVISION_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Recorder:
    """Record operation objects/SQL without a connection or execute-capable bind."""

    def __init__(self):
        self.metadata = sa.MetaData()
        self.context = MigrationContext.configure(dialect_name="postgresql")
        self.indexes = {}
        self.events = []

    def execute(self, statement):
        self.events.append(("sql", str(statement)))

    def create_table(self, name, *elements, **kwargs):
        assert kwargs == {"schema": "public"}
        table = sa.Table(name, self.metadata, *elements, schema="public")
        self.events.append(("create_table", name))
        return table

    def create_index(self, name, table_name, columns, **kwargs):
        assert f"public.{table_name}" in self.metadata.tables
        operation = ops.CreateIndexOp(name, table_name, columns, **kwargs)
        self.indexes[name] = operation.to_index(self.context)
        self.events.append(("create_index", name))

    def drop_table(self, name, **kwargs):
        assert kwargs == {"schema": "public"}
        self.events.append(("drop_table", name))


@pytest.fixture
def recorded(revision, monkeypatch):
    recorder = Recorder()
    monkeypatch.setattr(revision, "op", recorder)
    revision.upgrade()
    return revision, recorder


def constraint_signature(constraint):
    if isinstance(constraint, sa.CheckConstraint):
        return ("check", normalized(constraint.sqltext))
    if isinstance(constraint, sa.PrimaryKeyConstraint):
        return ("primary", tuple(constraint.columns.keys()), constraint.deferrable)
    if isinstance(constraint, sa.UniqueConstraint):
        return ("unique", tuple(constraint.columns.keys()), constraint.deferrable)
    if isinstance(constraint, sa.ForeignKeyConstraint):
        return (
            "foreign", tuple(constraint.columns.keys()), constraint.referred_table.name,
            tuple(element.column.name for element in constraint.elements),
            constraint.ondelete, constraint.onupdate, constraint.match, constraint.deferrable,
        )
    raise AssertionError(f"Unhandled constraint: {constraint}")


def test_initial_revision_is_a_frozen_snapshot(revision):
    assert revision.revision == "0001"
    assert revision.down_revision is None
    assert revision.branch_labels is None
    assert revision.depends_on is None
    tree = ast.parse(REVISION_FILE.read_text(encoding="utf-8"))
    imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
    assert not any(isinstance(node, ast.ImportFrom) and (node.module or "").startswith("app") for node in imports)
    assert "db.metadata" not in REVISION_FILE.read_text(encoding="utf-8")


def test_all_columns_and_constraints_match_models(recorded):
    revision, recorder = recorded
    assert set(revision.TABLE_ORDER) == set(db.metadata.tables)
    assert len(recorder.metadata.tables) == 9
    assert sum(len(table.columns) for table in recorder.metadata.tables.values()) == 100
    for name in revision.TABLE_ORDER:
        actual = recorder.metadata.tables[f"public.{name}"]
        expected = db.metadata.tables[name]
        assert list(actual.columns.keys()) == list(expected.columns.keys())
        for column in expected.columns:
            migrated = actual.c[column.name]
            assert migrated.type.compile(dialect=DIALECT) == column.type.compile(dialect=DIALECT)
            assert migrated.nullable is column.nullable
            assert migrated.primary_key is column.primary_key
            expected_default = str(column.server_default.arg) if column.server_default else None
            actual_default = str(migrated.server_default.arg) if migrated.server_default else None
            assert actual_default == expected_default
        assert {
            item.name: constraint_signature(item) for item in actual.constraints
        } == {
            item.name: constraint_signature(item) for item in expected.constraints
        }
    assert sum(len(table.foreign_key_constraints) for table in recorder.metadata.tables.values()) == 15
    assert sum(isinstance(item, sa.CheckConstraint) for table in recorder.metadata.tables.values() for item in table.constraints) == 99


def test_dependency_order_and_all_postgresql_indexes(recorded):
    revision, recorder = recorded
    seen = set()
    for kind, name in recorder.events:
        if kind == "create_table":
            table = recorder.metadata.tables[f"public.{name}"]
            assert all(fk.referred_table.name in seen for fk in table.foreign_key_constraints)
            seen.add(name)
    assert len(seen) == 9
    expected_indexes = {index.name: index for table in db.metadata.tables.values() for index in table.indexes}
    assert set(recorder.indexes) == set(expected_indexes)
    assert len(recorder.indexes) == 15
    for name, index in recorder.indexes.items():
        actual = CreateIndex(index).compile(dialect=DIALECT)
        expected = CreateIndex(expected_indexes[name]).compile(dialect=DIALECT)
        assert normalized(actual) == normalized(expected), name
    alert_sql = str(CreateIndex(recorder.indexes["uq_budget_alerts_active_scope"]).compile(dialect=DIALECT))
    assert "NULLS NOT DISTINCT" in alert_sql
    assert "WHERE resolved_at IS NULL" in alert_sql


def test_upgrade_creates_guards_before_granting_access(recorded):
    revision, recorder = recorded
    statements = [value for kind, value in recorder.events if kind == "sql"]
    assert len(revision.FUNCTIONS) == 8
    assert len(revision.TRIGGERS) == 23
    assert len({(table, name) for table, name, _ in revision.TRIGGERS}) == 23
    first_grant = next(index for index, statement in enumerate(statements) if statement.startswith("GRANT "))
    for name, (mode, _) in revision.FUNCTIONS.items():
        creation = next(index for index, statement in enumerate(statements) if statement.startswith(f"CREATE FUNCTION public.{name}()"))
        assert creation < first_grant
        assert f"SECURITY {mode}" in statements[creation]
        assert "SET search_path = pg_catalog, pg_temp AS $finset_body$" in statements[creation]
        assert "SET search_path = pg_catalog, public" not in statements[creation]
        assert f"ALTER FUNCTION public.{name}() OWNER TO finset_owner" in statements
        assert (
            f"REVOKE ALL ON FUNCTION public.{name}() "
            "FROM PUBLIC, finset_runtime, finset_migrator, finset_maintenance"
        ) in statements
    assert not any(statement.startswith("GRANT EXECUTE") for statement in statements)
    assert not any("CREATE OR REPLACE" in statement for statement in statements)


def application_references(body):
    """Source regression for these fixed bodies, not a PostgreSQL SQL parser."""
    text = " ".join(re.sub(r"--[^\n]*", "", body).split())
    identifier = r'(?:"[^"]+"|[A-Za-z_]\w*)'
    object_name = rf"{identifier}(?:\.{identifier})*"
    relations = re.findall(
        rf"(?<!DISTINCT )(?<!FOR )\b(?:FROM|JOIN|UPDATE|INSERT INTO|DELETE FROM|TRUNCATE TABLE)"
        rf"\s+(?:ONLY\s+)?({object_name})",
        text, re.I,
    )
    for relation in relations:
        assert relation.replace('"', '').startswith(("public.", "pg_catalog.")), relation

    identities = re.findall(
        r"\bCAST\s*\(\s*'([^']+)'\s+AS\s+(?:pg_catalog\.)?"
        r"(?:regclass|regtype|regproc|regprocedure)\s*\)", text, re.I,
    )
    assert all(identity.startswith("public.") for identity in identities)

    # Only count(*) is an unqualified function in these bodies. The remaining
    # bare parenthesized tokens are SQL/PLpgSQL constructs, not application calls.
    without_literals = re.sub(r"'(?:''|[^'])*'", "''", text)
    without_literals = re.sub(r"\bAS\s+[A-Za-z_]\w*\s*\([^)]*\)", "", without_literals, flags=re.I)
    calls = re.findall(rf"(?<![\w.])({object_name})\s*\(", without_literals)
    for call in calls:
        name = call.replace('"', '').lower()
        assert name.startswith(("pg_catalog.", "public.")) or name in {
            "count", "cast", "filter", "in", "if", "exists", "and", "or", "not", "from",
        }, call

    declarations = body.partition("BEGIN")[0]
    for data_type in re.findall(
        r"(?m)^[ \t]*[A-Za-z_]\w*[ \t]+([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?(?:\[\])?)",
        declarations,
    ):
        assert data_type.startswith(("pg_catalog.", "public.")) or data_type in {
            "text", "jsonb", "uuid", "uuid[]", "boolean", "timestamptz",
            "smallint", "integer", "bigint", "record", "name", "oid",
        }, data_type
    return set(re.findall(r"\bpublic\.[A-Za-z_]\w*", text))


@pytest.mark.parametrize("name,expected", [
    ("finset_guard_immutable", set()),
    ("finset_guard_category_mutation", {"public.categories"}),
    ("finset_guard_category_reference", {"public.categories"}),
    ("finset_guard_lifecycle", set()),
    ("finset_guard_plan_generation", {"public.plans"}),
    ("finset_prepare_plan_result", {"public.plans", "public.transactions"}),
    ("finset_allocate_plan_result", {"public.plans", "public.transactions"}),
    ("finset_check_plan_result", {"public.plans", "public.transactions"}),
])
def test_every_trigger_function_has_qualified_application_references(revision, name, expected):
    mode, body = revision.FUNCTIONS[name]
    assert mode == ("DEFINER" if name == "finset_allocate_plan_result" else "INVOKER")
    assert application_references(body) == expected
    assert "SET search_path" not in body
    assert "set_config" not in body


@pytest.mark.parametrize("name,original,replacement", [
    ("finset_prepare_plan_result", "FROM public.plans", "FROM plans"),
    ("finset_allocate_plan_result", "UPDATE public.plans", 'UPDATE "plans"'),
    ("finset_guard_plan_generation", "CAST('public.plans' AS regclass)", "CAST('plans' AS regclass)"),
    ("finset_guard_plan_generation", "pg_catalog.pg_trigger_depth()", "finset_guard_plan_generation()"),
])
def test_application_reference_regression_detects_unqualified_objects(revision, name, original, replacement):
    body = revision.FUNCTIONS[name][1]
    assert original in body
    with pytest.raises(AssertionError):
        application_references(body.replace(original, replacement))


def test_public_schema_create_is_rejected_explicitly_before_role_assumption():
    tree = ast.parse((MIGRATIONS / "env.py").read_text(encoding="utf-8"))
    preflight = next(
        ast.literal_eval(node.value) for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "ROLE_PREFLIGHT_SQL" for target in node.targets)
    )
    expected_guard = """
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_namespace AS ns
        CROSS JOIN LATERAL pg_catalog.aclexplode(
            COALESCE(ns.nspacl, pg_catalog.acldefault('n', ns.nspowner))
        ) AS acl
        WHERE ns.oid = public_oid AND acl.grantee = 0 AND acl.privilege_type = 'CREATE'
    ) THEN
        RAISE EXCEPTION 'PUBLIC must not have CREATE on schema public'
            USING ERRCODE = '42501';
    END IF;
    """
    assert " ".join(expected_guard.split()) in " ".join(preflight.split())
    assert "pg_catalog.has_schema_privilege(role_name, public_oid, 'CREATE')" in preflight
    assert not re.search(r"^\s*(?:GRANT|REVOKE)\s", preflight, re.I | re.M)


def test_role_grants_are_narrow_and_counter_is_not_directly_writable(recorded):
    revision, recorder = recorded
    statements = [value for kind, value in recorder.events if kind == "sql"]
    for table in revision.TABLE_ORDER:
        assert f"GRANT SELECT, DELETE ON TABLE public.{table} TO finset_runtime" in statements
        assert "id" not in revision.RUNTIME_INSERT_COLUMNS[table]
        assert "created_at" not in revision.RUNTIME_INSERT_COLUMNS[table]
        assert not set(revision.RUNTIME_UPDATE_COLUMNS[table]) & set(revision.IMMUTABLE_COLUMNS[table])
        assert not any(f"GRANT UPDATE ON TABLE public.{table} " in statement for statement in statements)
    assert "result_generation" not in revision.RUNTIME_INSERT_COLUMNS["plans"]
    assert "result_generation" not in revision.RUNTIME_UPDATE_COLUMNS["plans"]
    maintenance_grants = [statement for statement in statements if statement.startswith("GRANT ") and statement.endswith("TO finset_maintenance")]
    assert len(maintenance_grants) == 3
    assert all("ON TABLE public.finset_system_categories" in statement for statement in maintenance_grants)
    assert not any("GRANT ALL" in statement or "WITH GRANT OPTION" in statement for statement in statements)


def test_maintenance_view_and_invoker_authorization(recorded):
    revision, recorder = recorded
    statements = [value for kind, value in recorder.events if kind == "sql"]
    view = next(statement for statement in statements if "CREATE VIEW public.finset_system_categories" in statement)
    assert "security_barrier = true, security_invoker = false" in view
    assert "FROM public.categories WHERE owner_user_id IS NULL" in view
    assert "WITH LOCAL CHECK OPTION" in view
    assert "ALTER VIEW public.finset_system_categories OWNER TO finset_owner" in statements
    mode, body = revision.FUNCTIONS["finset_guard_category_mutation"]
    assert mode == "INVOKER"
    assert "pg_catalog.pg_has_role(current_user, 'finset_maintenance', 'USAGE')" in body
    assert "pg_catalog.pg_has_role(current_user, 'finset_runtime', 'USAGE')" in body
    assert "current_setting" not in body and "set_config" not in body


def test_category_reference_and_immutable_guards(revision):
    mode, body = revision.FUNCTIONS["finset_guard_category_reference"]
    assert mode == "INVOKER"
    assert "category_owner IS NOT NULL AND category_owner IS DISTINCT FROM NEW.user_id" in body
    assert "category_kind IS DISTINCT FROM expected_kind" in body
    assert "FOR SHARE OF c" in body
    assert "new_selection AND category_archived_at IS NOT NULL" in body
    assert "NEW.category_id IS DISTINCT FROM OLD.category_id" in body
    assert "OLD.user_id" in body
    assert "expected_kind := 'expense'" in body
    immutable = revision.FUNCTIONS["finset_guard_immutable"][1]
    assert "IS DISTINCT FROM" in immutable
    assert set(revision.IMMUTABLE_COLUMNS) == set(revision.TABLE_ORDER)
    assert "plan_id" in revision.IMMUTABLE_COLUMNS["transactions"]
    assert "category_type" in revision.IMMUTABLE_COLUMNS["categories"]
    assert "expires_at" in revision.IMMUTABLE_COLUMNS["login_sessions"]
    assert "target_email" in revision.IMMUTABLE_COLUMNS["auth_tokens"]


def test_allocator_runs_only_after_successful_insert(revision):
    mode, prepare = revision.FUNCTIONS["finset_prepare_plan_result"]
    assert mode == "INVOKER"
    assert "FOR UPDATE OF p" in prepare
    assert "p.user_id = NEW.user_id AND p.plan_type = NEW.transaction_type" in prepare
    assert "EXISTS (SELECT 1 FROM public.transactions WHERE plan_id = NEW.plan_id)" in prepare
    assert "SET result_generation" not in prepare
    mode, allocate = revision.FUNCTIONS["finset_allocate_plan_result"]
    assert mode == "DEFINER"
    assert "TG_WHEN <> 'AFTER'" in allocate
    assert "SET result_generation = result_generation + 1" in allocate
    assert "status = 'pending' AND result_generation IN (0, 1)" in allocate
    assert "IF affected <> 1" in allocate
    assert "SET status" not in allocate and "SET version" not in allocate
    assert any(name == "finset_40_allocate_plan_result" and definition.startswith("AFTER INSERT") for _, name, definition in revision.TRIGGERS)
    guard = revision.FUNCTIONS["finset_guard_plan_generation"][1]
    assert "current_user <> 'finset_owner' OR pg_catalog.pg_trigger_depth() < 2" in guard
    assert "NEW.result_generation <> OLD.result_generation + 1" in guard
    assert "OLD.result_generation NOT IN (0, 1)" in guard
    assert "NEW.result_generation IS DISTINCT FROM 0" in guard
    assert "current_setting" not in guard and "set_config" not in guard


def test_deferred_checks_use_final_rows_and_all_events(revision):
    mode, body = revision.FUNCTIONS["finset_check_plan_result"]
    assert mode == "INVOKER"
    assert "OLD.plan_id" in body and "NEW.plan_id" in body
    assert "FROM public.plans WHERE id = target_id" in body
    assert "FROM public.transactions WHERE plan_id = target_id" in body
    assert "plan_status = 'completed' AND active_results <> 1" in body
    assert "plan_status IN ('pending', 'cancelled') AND active_results <> 0" in body
    assert "generation = 0 AND retained <> 0" in body
    assert "IF NOT FOUND THEN" in body and "CONTINUE;" in body
    assert "FOR UPDATE" not in body
    triggers = [definition for _, name, definition in revision.TRIGGERS if name == "finset_90_plan_result_consistency"]
    assert len(triggers) == 2
    for definition in triggers:
        assert "AFTER INSERT OR UPDATE OR DELETE" in definition
        assert "DEFERRABLE INITIALLY DEFERRED" in definition
        assert " WHEN " not in definition


def test_lifecycle_guards_do_not_implement_authentication_or_money_workflows(revision):
    body = revision.FUNCTIONS["finset_guard_lifecycle"][1]
    assert "NEW.credential_version < OLD.credential_version" in body
    assert "NEW.last_activity_at < OLD.last_activity_at" in body
    assert "NEW.idle_expires_at < OLD.idle_expires_at" in body
    assert "OLD.revoked_at IS NOT NULL AND NEW.revoked_at IS NULL" in body
    assert "OLD.consumed_at IS NOT NULL AND NEW.consumed_at IS NULL" in body
    assert "OLD.resolved_at IS NOT NULL AND NEW.resolved_at IS NULL" in body
    assert "NEW.recoverable_until IS DISTINCT FROM OLD.recoverable_until" in body
    assert not re.search(r"\b(INSERT INTO|UPDATE public\.|DELETE FROM)\b", body)
    all_bodies = "\n".join(body for _, body in revision.FUNCTIONS.values())
    assert "1000000000" not in all_bodies and "100000000000" not in all_bodies


def test_downgrade_removes_dependencies_without_global_destruction(recorded):
    revision, recorder = recorded
    recorder.events.clear()
    revision.downgrade()
    events = recorder.events
    first_table = next(index for index, event in enumerate(events) if event[0] == "drop_table")
    last_trigger = max(index for index, event in enumerate(events) if event[0] == "sql" and event[1].startswith("DROP TRIGGER"))
    first_function = min(index for index, event in enumerate(events) if event[0] == "sql" and event[1].startswith("DROP FUNCTION"))
    assert last_trigger < first_function < first_table
    assert events[1] == ("sql", "DROP VIEW public.finset_system_categories RESTRICT")
    assert [name for kind, name in events if kind == "drop_table"] == list(reversed(revision.TABLE_ORDER))
    sql_text = "\n".join(value for kind, value in events if kind == "sql")
    assert "CASCADE" not in sql_text
    assert not re.search(r"\b(?:CREATE|ALTER|DROP)\s+(?:ROLE|DATABASE|SCHEMA)\b", sql_text, re.I)


@pytest.mark.parametrize("direction", ["upgrade", "downgrade"])
def test_full_alembic_offline_output_never_opens_an_engine(monkeypatch, direction):
    def forbidden_engine(*args, **kwargs):
        pytest.fail("Offline migration compilation must not create an engine.")

    monkeypatch.setattr(sa, "create_engine", forbidden_engine)
    monkeypatch.delenv("FINSET_MIGRATION_DATABASE_URL", raising=False)
    output = StringIO()
    configuration = Config(str(MIGRATIONS / "alembic.ini"), output_buffer=output, stdout=StringIO())
    if direction == "upgrade":
        command.upgrade(configuration, "head", sql=True)
    else:
        command.downgrade(configuration, "0001:base", sql=True)
    rendered = output.getvalue()
    assert "SET LOCAL ROLE finset_owner" in rendered
    assert "BEGIN;" in rendered and "COMMIT;" in rendered
    assert "ROLE_PREFLIGHT_SQL" not in rendered
    assert "Required externally provisioned role is missing" in rendered
    assert "PUBLIC must not have CREATE on schema public" in rendered
    assert rendered.index("PUBLIC must not have CREATE on schema public") < rendered.index("SET LOCAL ROLE finset_owner")
    assert "SET LOCAL search_path = pg_catalog, pg_temp;" in rendered
    assert "END;\n$finset_roles$;" in rendered
    assert "END;\n$finset_owner_check$;" in rendered
    assert not re.search(r"\b(?:CREATE|ALTER|DROP)\s+ROLE\b", rendered, re.I)
    if direction == "upgrade":
        assert rendered.index("SET LOCAL ROLE finset_owner") < rendered.index("CREATE TABLE public.alembic_version")
        assert "CREATE TABLE public.users" in rendered
        assert "NULLS NOT DISTINCT WHERE resolved_at IS NULL" in rendered
        assert rendered.count("CREATE FUNCTION public.finset_") == 8
        assert rendered.count("SET search_path = pg_catalog, pg_temp AS $finset_body$") == 8
        assert "SET search_path = pg_catalog, public, pg_temp" not in rendered
        assert rendered.count("CREATE CONSTRAINT TRIGGER finset_90_plan_result_consistency") == 2
    else:
        assert "DROP TABLE public.users" in rendered
        assert "DROP SCHEMA" not in rendered


def test_environment_requires_separate_credentials_and_role_provisioning():
    source = (MIGRATIONS / "env.py").read_text(encoding="utf-8")
    assert 'os.environ.get("FINSET_MIGRATION_DATABASE_URL")' in source
    assert 'os.environ.get("DEV_DATABASE_URL")' not in source
    assert "get_engine" not in source
    assert "NOT inherit_option AND NOT admin_option" in source
    assert "'finset_migrator', 'finset_owner', 'SET'" in source
    assert "'finset_migrator', 'finset_owner', 'USAGE'" in source
    assert "nspowner = owner_oid" in source
    assert "role_row.rolcanlogin" in source
    assert "defaults.defaclobjtype = 'f' AND permission.grantee = 0" in source
    assert not re.search(r"\b(?:CREATE|ALTER|DROP)\s+ROLE\b", source, re.I)
