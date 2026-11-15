"""Rollback-only runtime CRUD and row-local constraints, without app services."""

from datetime import date
from uuid import UUID

import pytest


pytestmark = [pytest.mark.integration, pytest.mark.finset_integration]


def test_user_crud_and_safe_row_shape(runtime, data, case):
    email = case.email("user")
    user = data.user(
        full_name=case.label("user_name"), email=email, appearance="system",
        currency="NGN", date_format="DD/MM/YYYY", week_start_day=1,
    )
    row = runtime.get(user)
    assert set(row) == {
        "id", "full_name", "email", "email_verified_at", "credential_version",
        "appearance", "currency", "date_format", "week_start_day",
        "last_successful_login_at", "created_at", "updated_at",
    }
    assert isinstance(user.id, UUID)
    assert user.table == "users"
    assert user.owner_id == user.id == row["id"]
    assert row["email"] == email
    assert row["credential_version"] == 1
    assert row["appearance"] == "system"
    assert row["currency"] == "NGN"
    assert row["date_format"] == "DD/MM/YYYY"
    assert row["week_start_day"] == 1
    assert row["email_verified_at"] is None
    assert row["last_successful_login_at"] is None
    now = runtime.clock()
    assert now.utcoffset() is not None
    assert row["created_at"] == now
    assert row["updated_at"] >= row["created_at"]

    new_email = case.email("renamed_user")
    user = runtime.update(
        user, full_name=case.label("renamed_user"), email=new_email,
        appearance="dark", date_format="YYYY-MM-DD", week_start_day=7,
        email_verified_at=now, last_successful_login_at=now, updated_at=now,
    )
    row = runtime.get(user)
    assert row["full_name"] == user.values["full_name"]
    assert row["email"] == new_email
    assert row["appearance"] == "dark"
    assert row["date_format"] == "YYYY-MM-DD"
    assert row["week_start_day"] == 7
    assert row["email_verified_at"] == row["last_successful_login_at"] == now
    assert runtime.rows("users", email=new_email) == [row]
    assert runtime.count("users", email=new_email) == 1
    runtime.check_constraints()
    assert runtime.delete(user) == 1
    assert runtime.get(user) is None
    assert runtime.count("users", email=new_email) == 0


@pytest.mark.parametrize("kind", ["income", "expense"])
def test_manual_plan_transaction_and_category_crud(runtime, data, case, kind):
    user = data.user()
    category = data.category(user, kind=kind, name=case.label("manual_category"))
    plan = data.plan(
        user, kind=kind, category=category, expected_amount=1500,
        expected_date=date(2026, 11, 10), description=None,
    )
    transaction = data.transaction(
        user, kind=kind, category=category, amount=1200,
        transaction_date=date(2026, 11, 11), plan_id=None, description=None,
    )
    for record in (category, plan, transaction):
        assert isinstance(record.id, UUID)
        assert record.owner_id == user.id
        assert runtime.get(record)["id"] == record.id
    assert plan.values["plan_type"] == kind
    assert plan.values["expected_amount_kobo"] == 1500
    assert plan.values["status"] == "pending"
    assert plan.values["completed_at"] is None
    assert plan.values["description"] is None
    assert transaction.values["transaction_type"] == kind
    assert transaction.values["amount_kobo"] == 1200
    assert transaction.values["description"] is None
    assert transaction.values["plan_id"] is None
    assert transaction.values["deleted_at"] is None
    assert transaction.values["recoverable_until"] is None

    category = runtime.update(category, name=case.label("renamed_category"))
    plan = runtime.update(
        plan, expected_amount_kobo=2000, expected_date=date(2026, 11, 12),
        description=case.label("plan_note"),
    )
    transaction = runtime.update(
        transaction, amount_kobo=1800, transaction_date=date(2026, 11, 12),
        description=case.label("manual_note"),
    )
    assert runtime.get(category)["name"] == category.values["name"]
    assert runtime.get(plan)["expected_amount_kobo"] == 2000
    assert runtime.get(transaction)["amount_kobo"] == 1800
    assert runtime.get(transaction)["plan_id"] is None
    assert {row["id"] for row in runtime.rows("plans", user_id=user.id)} == {plan.id}
    assert {row["id"] for row in runtime.rows("transactions", user_id=user.id)} == {
        transaction.id,
    }
    runtime.check_constraints()
    for record in (transaction, plan, category, user):
        assert runtime.delete(record) == 1
        assert runtime.get(record) is None
    runtime.check_constraints()


def test_budget_limit_alert_crud(runtime, data):
    user = data.user()
    category = data.category(user)
    budget = data.budget(user, category=category, month=date(2026, 11, 1), allocation=50000)
    limit = data.limit(
        user, budget, start=date(2026, 11, 10), end=date(2026, 11, 11), amount=10000,
    )
    alert = data.alert(
        user, budget, limit=limit,
        period_start=date(2026, 11, 10), period_end=date(2026, 11, 11),
    )
    assert budget.values["month_start"] == date(2026, 11, 1)
    assert budget.values["allocation_kobo"] == 50000
    assert budget.values["warning_percent"] == 80
    assert budget.values["archived_at"] is None
    assert limit.values["budget_id"] == budget.id
    assert limit.values["period_type"] == "daily"
    assert limit.values["week_start_day"] is None
    assert limit.values["archived_at"] is None
    assert alert.values["budget_id"] == budget.id
    assert alert.values["budget_limit_id"] == limit.id
    assert alert.values["alert_type"] == "warning"
    assert alert.values["threshold_percent"] == 80
    assert alert.values["read_at"] is None
    assert alert.values["resolved_at"] is None
    for record in (budget, limit, alert):
        assert isinstance(record.id, UUID)
        assert record.owner_id == user.id
        assert runtime.count(record.table, user_id=user.id) == 1

    budget = runtime.update(budget, allocation_kobo=60000)
    limit = runtime.update(limit, limit_kobo=12000)
    alert = runtime.update(alert, read_at=runtime.clock())
    assert runtime.get(budget)["allocation_kobo"] == 60000
    assert runtime.get(limit)["limit_kobo"] == 12000
    assert runtime.get(alert)["read_at"] == runtime.clock()
    runtime.check_constraints()
    for record in (alert, limit, budget, category, user):
        assert runtime.delete(record) == 1
        assert runtime.get(record) is None


@pytest.mark.parametrize("column,value,sqlstate,constraint", [
    ("full_name", None, "23502", None),
    ("email", None, "23502", None),
    ("password_hash", None, "23502", None),
    ("appearance", None, "23502", None),
    ("full_name", "   ", "23514", "ck_users_full_name_nonempty"),
    ("email", "", "23514", "ck_users_email_normalized"),
    ("password_hash", "", "23514", "ck_users_password_hash_length"),
    ("appearance", "sepia", "23514", "ck_users_appearance"),
    ("currency", "USD", "23514", "ck_users_currency"),
    ("date_format", "DD-MM-YYYY", "23514", "ck_users_date_format"),
    ("week_start_day", 2, "23514", "ck_users_week_start_day"),
])
def test_user_required_values_and_enums(runtime, data, column, value, sqlstate, constraint):
    with runtime.rejects(sqlstate, constraint=constraint):
        data.user(**{column: value})


@pytest.mark.parametrize("variant", ["uppercase", "padded"])
def test_email_must_arrive_normalized(runtime, data, case, variant):
    email = case.email("normalized")
    invalid = email.upper() if variant == "uppercase" else f" {email} "
    with runtime.rejects("23514", constraint="ck_users_email_normalized"):
        data.user(email=invalid)


def test_normalized_email_is_unique_on_insert_and_update(runtime, data, case):
    email = case.email("unique_email")
    original = data.user(email=email)
    other = data.user()
    with runtime.rejects("23505", constraint="uq_users_email"):
        data.user(email=email)
    with runtime.rejects("23505", constraint="uq_users_email"):
        runtime.update(other, email=email)
    assert runtime.get(original)["email"] == email
    assert runtime.get(other)["email"] == other.values["email"]


@pytest.mark.parametrize("builder,column", [
    ("category", "name"),
    ("plan", "expected_date"),
    ("plan", "expected_amount_kobo"),
    ("transaction", "transaction_type"),
    ("transaction", "transaction_date"),
    ("transaction", "amount_kobo"),
    ("budget", "allocation_kobo"),
    ("limit", "start_date"),
    ("limit", "end_date"),
    ("limit", "limit_kobo"),
])
def test_required_mutable_financial_columns_reject_null(runtime, data, builder, column):
    user = data.user()
    args = (user, data.budget(user)) if builder == "limit" else (user,)
    record = getattr(data, builder)(*args)
    with runtime.rejects("23502"):
        runtime.update(record, **{column: None})


@pytest.mark.parametrize("builder,column,value", [
    ("category", "category_type", "other"),
    ("plan", "plan_type", "other"),
    ("transaction", "transaction_type", "other"),
    ("limit", "period_type", "yearly"),
    ("alert", "alert_type", "notice"),
])
def test_financial_type_enums(runtime, data, builder, column, value):
    user = data.user()
    args = (user, data.budget(user)) if builder in ("limit", "alert") else (user,)
    # A bad enum can also fail a dependent row-shape CHECK; only the SQLSTATE is stable.
    with runtime.rejects("23514"):
        getattr(data, builder)(*args, **{column: value})


@pytest.mark.parametrize("status,sqlstate", [(None, "23502"), ("paused", "23514")])
def test_plan_status_is_required_and_constrained(runtime, data, status, sqlstate):
    user = data.user()
    plan = data.plan(user)
    plan = runtime.update(plan, status="cancelled")
    assert runtime.get(plan)["completed_at"] is None
    runtime.check_constraints()
    with runtime.rejects(sqlstate):
        runtime.update(plan, status=status)


@pytest.mark.parametrize("builder", ["plan", "transaction"])
@pytest.mark.parametrize("source", [None, "", "   "])
def test_income_requires_a_nonblank_source(runtime, data, builder, source):
    user = data.user()
    with runtime.rejects("23514", constraint=f"ck_{builder}s_income_source"):
        getattr(data, builder)(user, source=source)


@pytest.mark.parametrize("builder", ["plan", "transaction"])
def test_expense_requires_a_category(runtime, data, builder):
    user = data.user()
    category = data.category(user)
    with runtime.rejects("23514", constraint=f"ck_{builder}s_expense_category"):
        getattr(data, builder)(user, kind="expense", category=category, category_id=None)


@pytest.mark.parametrize("builder", ["plan", "transaction"])
def test_income_allows_null_category_and_description(runtime, data, case, builder):
    user = data.user()
    source = case.label("income_source")
    record = getattr(data, builder)(user, category_id=None, description=None, source=source)
    row = runtime.get(record)
    assert row["category_id"] is None
    assert row["description"] is None
    assert row["source"] == source
    runtime.check_constraints()
