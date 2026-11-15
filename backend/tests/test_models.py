"""Compare declarations to the approved schema without executing SQL."""

from pathlib import Path
import re
from uuid import uuid4
import warnings

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session, configure_mappers
from sqlalchemy.schema import CreateIndex, CreateTable

from app import create_app
from app.extensions import db
from app.models import (
    AuthToken,
    BudgetAlert,
    BudgetLimit,
    Category,
    LoginSession,
    MonthlyBudget,
    Plan,
    Transaction,
    User,
)


MODELS = (User, Category, Transaction, Plan, MonthlyBudget, BudgetLimit, BudgetAlert, LoginSession, AuthToken)
TABLES = {model.__tablename__: model.__table__ for model in MODELS}
DIALECT = postgresql.dialect()
SCHEMA_DOCUMENT = Path(__file__).resolve().parents[2] / "docs" / "database-schema-design.md"


def documented_columns():
    """Read only the nine column-specification tables, not narrative examples."""
    tables = {}
    current = None
    for line in SCHEMA_DOCUMENT.read_text(encoding="utf-8").splitlines():
        heading = re.fullmatch(r"### 4\.\d+ `([^`]+)`", line)
        if heading:
            current = heading.group(1)
            tables[current] = {}
        elif line.startswith("## ") or line.startswith("### "):
            current = None
        elif current and line.startswith("| `"):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            assert len(cells) == 6, f"Unexpected schema table row: {line}"
            name, data_type, nullable, default, _, _ = cells
            default = default.replace("`", "")
            tables[current][name.strip("`")] = {
                "type": data_type.strip("`").upper().replace("TIMESTAMPTZ", "TIMESTAMP WITH TIME ZONE"),
                "nullable": nullable.startswith("Yes"),
                "default": None if default == "NULL" or default.startswith("None") else default,
            }
    return tables


def sql(expression):
    return str(expression.compile(dialect=DIALECT, compile_kwargs={"literal_binds": True}))


def test_exactly_nine_models_match_the_documented_tables():
    assert set(TABLES) == set(documented_columns()) == set(db.metadata.tables)
    assert len(list(db.Model.registry.mappers)) == 9
    assert sum(len(table.columns) for table in TABLES.values()) == 100


@pytest.mark.parametrize("model", MODELS, ids=lambda model: model.__name__)
def test_columns_types_nullability_and_server_defaults(model):
    expected = documented_columns()[model.__tablename__]
    table = model.__table__
    assert list(table.columns.keys()) == list(expected)
    for column in table.columns:
        specification = expected[column.name]
        assert column.type.compile(dialect=DIALECT) == specification["type"], column.name
        assert column.nullable is specification["nullable"], column.name
        actual_default = sql(column.server_default.arg) if column.server_default else None
        assert actual_default == specification["default"], column.name
        assert column.default is None, "Do not add undocumented client-side defaults."
        assert column.onupdate is None, "Update/version workflows belong to later services."
    assert tuple(table.primary_key.columns.keys()) == ("id",)
    assert isinstance(table.c.id.type, sa.Uuid)
    assert table.c.id.type.as_uuid is True


def test_mapper_configuration_and_factory_are_database_free(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "model-test-only-secret-not-for-deployment-123456")
    monkeypatch.setenv("TEST_DATABASE_URL", "postgresql+psycopg://model_test@127.0.0.1:1/finset_test")
    monkeypatch.delenv("DEV_DATABASE_URL", raising=False)
    with warnings.catch_warnings():
        warnings.simplefilter("error", sa.exc.SAWarning)
        app = create_app("testing", load_env=False)
        configure_mappers()
    assert app.extensions["sqlalchemy"] is db
    assert app.testing
    assert not list(app.url_map.iter_rules())


def test_foreign_key_catalogue_matches_owner_and_deletion_rules():
    expected = {
        ("categories", ("owner_user_id",), "users", ("id",), "RESTRICT"),
        ("transactions", ("user_id",), "users", ("id",), "RESTRICT"),
        ("transactions", ("category_id",), "categories", ("id",), "RESTRICT"),
        ("transactions", ("user_id", "plan_id", "transaction_type"), "plans", ("user_id", "id", "plan_type"), "RESTRICT"),
        ("plans", ("user_id",), "users", ("id",), "RESTRICT"),
        ("plans", ("category_id",), "categories", ("id",), "RESTRICT"),
        ("monthly_budgets", ("user_id",), "users", ("id",), "RESTRICT"),
        ("monthly_budgets", ("category_id",), "categories", ("id",), "RESTRICT"),
        ("budget_limits", ("user_id",), "users", ("id",), "RESTRICT"),
        ("budget_limits", ("user_id", "budget_id"), "monthly_budgets", ("user_id", "id"), "RESTRICT"),
        ("budget_alerts", ("user_id",), "users", ("id",), "RESTRICT"),
        ("budget_alerts", ("user_id", "budget_id"), "monthly_budgets", ("user_id", "id"), "RESTRICT"),
        ("budget_alerts", ("user_id", "budget_id", "budget_limit_id"), "budget_limits", ("user_id", "budget_id", "id"), "RESTRICT"),
        ("login_sessions", ("user_id",), "users", ("id",), "CASCADE"),
        ("auth_tokens", ("user_id",), "users", ("id",), "CASCADE"),
    }
    actual = set()
    for table in TABLES.values():
        for key in table.foreign_key_constraints:
            actual.add((
                table.name, tuple(element.parent.name for element in key.elements),
                key.referred_table.name, tuple(element.column.name for element in key.elements),
                key.ondelete,
            ))
            assert key.onupdate == "RESTRICT"
            assert key.deferrable is False
            assert key.match == "SIMPLE"
            assert key.name
    assert actual == expected


def test_unique_keys_include_deleted_and_archived_records():
    expected = {
        "users": {("email",)},
        "categories": set(),
        "transactions": {("plan_id",)},
        "plans": {("user_id", "id", "plan_type")},
        "monthly_budgets": {("user_id", "month_start", "category_id"), ("user_id", "id")},
        "budget_limits": {("user_id", "budget_id", "id")},
        "budget_alerts": set(),
        "login_sessions": {("token_hash",)},
        "auth_tokens": {("token_hash",)},
    }
    for name, table in TABLES.items():
        constraints = [key for key in table.constraints if isinstance(key, sa.UniqueConstraint)]
        assert {tuple(key.columns.keys()) for key in constraints} == expected[name]
        for key in constraints:
            assert key.deferrable is False
            assert key.name
    assert not any(
        tuple(column.name for column in index.columns) == ("plan_id",)
        for index in TABLES["transactions"].indexes
    ), "The plan reservation must not become an active-only partial index."


def test_optional_links_cannot_omit_mandatory_owner_columns():
    assert TABLES["categories"].c.owner_user_id.nullable
    assert TABLES["transactions"].c.plan_id.nullable
    assert TABLES["budget_alerts"].c.budget_limit_id.nullable
    for name in ("transactions", "plans", "monthly_budgets", "budget_limits", "budget_alerts"):
        assert not TABLES[name].c.user_id.nullable
    assert not TABLES["transactions"].c.transaction_type.nullable
    assert not TABLES["budget_alerts"].c.budget_id.nullable
    assert not TABLES["budget_limits"].c.budget_id.nullable


def test_relationship_inventory_and_no_persistence_cascades():
    expected = {
        User: {"categories", "transactions", "plans", "monthly_budgets", "budget_limits", "budget_alerts", "login_sessions", "auth_tokens"},
        Category: {"owner", "transactions", "plans", "monthly_budgets"},
        Transaction: {"user", "category", "plan"},
        Plan: {"user", "category", "transaction"},
        MonthlyBudget: {"user", "category", "limits", "alerts"},
        BudgetLimit: {"user", "budget", "alerts"},
        BudgetAlert: {"user", "budget", "limit"},
        LoginSession: {"user"},
        AuthToken: {"user"},
    }
    for model, names in expected.items():
        relationships = sa.inspect(model).relationships
        assert set(relationships.keys()) == names
        for relationship in relationships:
            assert relationship.viewonly
            assert not relationship.cascade
            assert relationship.back_populates
    assert not sa.inspect(Plan).relationships.transaction.uselist
    assert not sa.inspect(Transaction).relationships.plan.uselist
    assert "deleted_at" not in sql(sa.inspect(Plan).relationships.transaction.primaryjoin)


@pytest.mark.parametrize("model,attribute,pairs", [
    (Transaction, "plan", {("user_id", "user_id"), ("plan_id", "id"), ("transaction_type", "plan_type")}),
    (BudgetLimit, "budget", {("user_id", "user_id"), ("budget_id", "id")}),
    (BudgetAlert, "budget", {("user_id", "user_id"), ("budget_id", "id")}),
    (BudgetAlert, "limit", {("user_id", "user_id"), ("budget_id", "budget_id"), ("budget_limit_id", "id")}),
])
def test_composite_relationship_joins(model, attribute, pairs):
    relationship = sa.inspect(model).relationships[attribute]
    assert {(local.name, remote.name) for local, remote in relationship.local_remote_pairs} == pairs


def test_navigation_does_not_reassign_ownership_or_add_children():
    owner = User(id=uuid4())
    original_owner = uuid4()
    transaction = Transaction(user_id=original_owner)
    owner.transactions.append(transaction)
    transaction.user = owner
    with Session() as session:
        session.add(owner)
        assert list(session.new) == [owner]
        assert transaction.user_id == original_owner
        assert sa.inspect(transaction).transient


def test_every_date_and_timestamp_has_a_finite_check():
    for table in TABLES.values():
        checks = " ".join(str(check.sqltext) for check in table.constraints if isinstance(check, sa.CheckConstraint))
        for column in table.columns:
            if isinstance(column.type, (sa.Date, sa.DateTime)):
                assert f"isfinite({column.name})" in checks, f"{table.name}.{column.name}"
            if isinstance(column.type, sa.DateTime):
                assert column.type.timezone is True
            if column.name.endswith("_kobo"):
                assert isinstance(column.type, sa.BigInteger)
                assert f"{column.name} >= 1" in checks
        assert "1000000000" not in checks
        assert "100000000000" not in checks
        assert "current_date" not in checks.lower()


def test_nullable_state_checks_are_not_null_escape_holes():
    checks = {
        constraint.name: str(constraint.sqltext)
        for table in TABLES.values()
        for constraint in table.constraints
        if isinstance(constraint, sa.CheckConstraint)
    }
    assert "source IS NOT NULL" in checks["ck_transactions_income_source"]
    assert "source IS NOT NULL" in checks["ck_plans_income_source"]
    assert "deleted_at IS NOT NULL AND recoverable_until IS NOT NULL" in checks["ck_transactions_recovery_state"]
    assert "completed_at IS NOT NULL" in checks["ck_plans_completion_state"]
    assert "week_start_day IS NOT NULL AND week_start_day IN (1, 7)" in checks["ck_budget_limits_window_shape"]
    assert "target_email IS NOT NULL" in checks["ck_auth_tokens_target_email"]
    assert checks["ck_auth_tokens_terminal_state"] == "consumed_at IS NULL OR revoked_at IS NULL"
    assert checks["ck_plans_result_generation_range"] == "result_generation BETWEEN 0 AND 2"


def test_postgresql_index_declarations():
    indexes = {index.name: index for table in TABLES.values() for index in table.indexes}
    assert set(indexes) == {
        "uq_categories_system_name_type", "uq_categories_custom_owner_name",
        "ix_transactions_user_date_active", "ix_transactions_user_category_date_active",
        "ix_transactions_user_deleted", "ix_transactions_recovery_deadline",
        "ix_plans_user_status_date", "uq_budget_limits_active_start",
        "uq_budget_alerts_active_scope", "ix_budget_alerts_user_created",
        "ix_login_sessions_user", "ix_login_sessions_invalidation",
        "uq_auth_tokens_outstanding_purpose", "ix_auth_tokens_user", "ix_auth_tokens_invalidation",
    }
    compiled = {name: str(CreateIndex(index).compile(dialect=DIALECT)) for name, index in indexes.items()}
    assert "(owner_user_id, lower(btrim(name)))" in compiled["uq_categories_custom_owner_name"]
    assert "WHERE owner_user_id IS NOT NULL" in compiled["uq_categories_custom_owner_name"]
    assert "WHERE owner_user_id IS NULL" in compiled["uq_categories_system_name_type"]
    assert "NULLS NOT DISTINCT WHERE resolved_at IS NULL" in compiled["uq_budget_alerts_active_scope"]
    assert "WHERE archived_at IS NULL" in compiled["uq_budget_limits_active_start"]
    assert "WHERE consumed_at IS NULL AND revoked_at IS NULL" in compiled["uq_auth_tokens_outstanding_purpose"]
    assert "least(expires_at, idle_expires_at, revoked_at)" in compiled["ix_login_sessions_invalidation"]
    assert "least(expires_at, consumed_at, revoked_at)" in compiled["ix_auth_tokens_invalidation"]
    assert not any("now()" in statement.lower() for statement in compiled.values())


@pytest.mark.parametrize("model", MODELS, ids=lambda model: model.__name__)
def test_postgresql_table_definitions_compile_without_execution(model):
    table = model.__table__
    statement = str(CreateTable(table).compile(dialect=DIALECT))
    assert f"CREATE TABLE {table.name}" in statement
    assert "gen_random_uuid()" in statement
    assert "PRIMARY KEY (id) NOT DEFERRABLE" in statement
    assert "CREATE TRIGGER" not in statement
    assert "CREATE FUNCTION" not in statement
    for constraint in table.constraints:
        assert constraint.name
        assert len(constraint.name) <= 63
    assert not list(table.dispatch.before_create)
    assert not list(table.dispatch.after_create)
