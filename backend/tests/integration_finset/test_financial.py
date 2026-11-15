"""Integer storage and calendar/index rules, not application money or TTL policy."""

from datetime import date, timedelta
from decimal import Decimal
from functools import partial

import pytest


pytestmark = [pytest.mark.integration, pytest.mark.finset_integration]

BIGINT_MAX = (1 << 63) - 1


@pytest.fixture(params=[
    ("transaction", "amount_kobo", "ck_transactions_amount_positive"),
    ("plan", "expected_amount_kobo", "ck_plans_expected_amount_positive"),
    ("budget", "allocation_kobo", "ck_monthly_budgets_allocation_positive"),
    ("limit", "limit_kobo", "ck_budget_limits_amount_positive"),
], ids=["transaction", "plan", "budget", "limit"])
def money_field(request, data):
    factory, column, constraint = request.param
    user = data.user()
    options = {}
    if factory == "budget":
        options["category"] = data.category(user)
    elif factory == "limit":
        options["budget"] = data.budget(user, allocation=BIGINT_MAX)
    return partial(getattr(data, factory), user, **options), column, constraint


@pytest.mark.parametrize("amount", [1, (1 << 53) + 1, BIGINT_MAX])
def test_positive_bigint_storage_is_exact(runtime, money_field, amount):
    create, column, _ = money_field
    record = create(**{column: amount})
    stored = runtime.get(record)[column]
    assert type(stored) is int
    assert stored == amount
    runtime.check_constraints()


@pytest.mark.parametrize("operation", ["insert", "update"])
@pytest.mark.parametrize("amount", [0, -1])
def test_money_rejects_nonpositive_values(runtime, money_field, operation, amount):
    create, column, constraint = money_field
    record = create() if operation == "update" else None
    with runtime.rejects("23514", constraint=constraint):
        if operation == "insert":
            create(**{column: amount})
        else:
            runtime.update(record, **{column: amount})


@pytest.mark.parametrize("operation", ["insert", "update"])
@pytest.mark.parametrize("amount", [1 << 63, -(1 << 63) - 1])
def test_money_rejects_signed_bigint_overflow(runtime, money_field, operation, amount):
    create, column, _ = money_field
    record = create() if operation == "update" else None
    with runtime.rejects("22003"):
        if operation == "insert":
            create(**{column: amount})
        else:
            runtime.update(record, **{column: amount})


def test_sum_bigint_remains_exact_beyond_int64_and_float_precision(runtime, data):
    user = data.user()
    amounts = (BIGINT_MAX, BIGINT_MAX, 1)
    records = [data.transaction(user, amount=amount) for amount in amounts]
    other = data.user()
    data.transaction(other, amount=BIGINT_MAX)
    total = runtime.sum("transactions", "amount_kobo", user_id=user.id)
    assert type(total) in (int, Decimal)
    assert total == sum(amounts) == (1 << 64) - 1
    rows = runtime.rows("transactions", user_id=user.id)
    assert {row["id"] for row in rows} == {record.id for record in records}
    assert sorted(row["amount_kobo"] for row in rows) == sorted(amounts)
    runtime.check_constraints()


@pytest.mark.parametrize("day", [2, 15, 30])
def test_monthly_budget_requires_first_of_month(runtime, data, day):
    user = data.user()
    category = data.category(user)
    with runtime.rejects("23514", constraint="ck_monthly_budgets_month_start"):
        data.budget(user, category=category, month=date(2026, 11, day))


@pytest.mark.parametrize("archived", [False, True], ids=["active", "archived"])
def test_monthly_budget_reserves_its_month_and_category(runtime, data, archived):
    user = data.user()
    category = data.category(user)
    budget = data.budget(user, category=category, month=date(2026, 11, 1))
    if archived:
        budget = runtime.update(budget, archived_at=runtime.clock())
    with runtime.rejects("23505", constraint="uq_monthly_budgets_user_month_category"):
        data.budget(user, category=category, month=date(2026, 11, 1))
    assert runtime.get(budget)["archived_at"] == budget.values["archived_at"]
    assert runtime.count(
        "monthly_budgets", user_id=user.id, category_id=category.id,
        month_start=date(2026, 11, 1),
    ) == 1


@pytest.mark.parametrize("kind,start,end,weekday", [
    pytest.param("daily", date(2026, 11, 10), date(2026, 11, 11), None, id="daily"),
    pytest.param("daily", date(2026, 11, 30), date(2026, 12, 1), None, id="last-day"),
    pytest.param("weekly", date(2026, 11, 2), date(2026, 11, 9), 1, id="monday-week"),
    pytest.param("weekly", date(2026, 11, 1), date(2026, 11, 2), 1, id="monday-clipped-start"),
    pytest.param("weekly", date(2026, 11, 30), date(2026, 12, 1), 1, id="monday-clipped-end"),
    pytest.param("weekly", date(2026, 11, 1), date(2026, 11, 8), 7, id="sunday-week"),
    pytest.param("weekly", date(2026, 11, 29), date(2026, 12, 1), 7, id="sunday-clipped-end"),
])
def test_daily_and_clipped_weekly_local_windows(runtime, data, kind, start, end, weekday):
    user = data.user()
    budget = data.budget(user, month=date(2026, 11, 1))
    limit = data.limit(user, budget, kind=kind, start=start, end=end, week_start_day=weekday)
    row = runtime.get(limit)
    assert row["period_type"] == kind
    assert row["start_date"] == start
    assert row["end_date"] == end
    assert row["week_start_day"] == weekday
    runtime.check_constraints()


@pytest.mark.parametrize("kind,start,end,weekday,constraint", [
    pytest.param(
        "daily", date(2026, 11, 10), date(2026, 11, 12), None,
        "ck_budget_limits_window_shape", id="daily-two-days",
    ),
    pytest.param(
        "daily", date(2026, 11, 10), date(2026, 11, 11), 1,
        "ck_budget_limits_window_shape", id="daily-with-week-start",
    ),
    pytest.param(
        "weekly", date(2026, 11, 2), date(2026, 11, 9), None,
        "ck_budget_limits_window_shape", id="weekly-null-week-start",
    ),
    pytest.param(
        "weekly", date(2026, 11, 3), date(2026, 11, 10), 2,
        "ck_budget_limits_window_shape", id="weekly-invalid-week-start",
    ),
    pytest.param(
        "weekly", date(2026, 11, 3), date(2026, 11, 9), 1,
        "ck_budget_limits_window_shape", id="weekly-unaligned-start",
    ),
    pytest.param(
        "weekly", date(2026, 11, 2), date(2026, 11, 8), 1,
        "ck_budget_limits_window_shape", id="weekly-unaligned-end",
    ),
    pytest.param(
        "weekly", date(2026, 11, 2), date(2026, 11, 16), 1,
        "ck_budget_limits_window_shape", id="weekly-too-long",
    ),
    pytest.param(
        "weekly", date(2026, 11, 30), date(2026, 12, 7), 1,
        "ck_budget_limits_single_month", id="weekly-crosses-month",
    ),
])
def test_limit_rejects_invalid_local_windows(runtime, data, kind, start, end, weekday, constraint):
    user = data.user()
    budget = data.budget(user)
    # Direct values preserve deliberate NULLs rather than using a helper's week default.
    with runtime.rejects("23514", constraint=constraint):
        runtime.insert(
            "budget_limits", user_id=user.id, budget_id=budget.id, period_type=kind,
            start_date=start, end_date=end, week_start_day=weekday, limit_kobo=1000,
        )


@pytest.mark.parametrize("kind,start,end,weekday", [
    ("daily", date(2026, 11, 2), date(2026, 11, 3), None),
    ("weekly", date(2026, 11, 2), date(2026, 11, 9), 1),
])
def test_limit_active_start_is_reserved_until_archival(runtime, data, kind, start, end, weekday):
    user = data.user()
    budget = data.budget(user)
    options = {"kind": kind, "start": start, "end": end, "week_start_day": weekday}
    original = data.limit(user, budget, **options)
    with runtime.rejects("23505", constraint="uq_budget_limits_active_start"):
        data.limit(user, budget, **options)
    original = runtime.update(original, archived_at=runtime.clock())
    replacement = data.limit(user, budget, **options)
    with runtime.rejects("23505", constraint="uq_budget_limits_active_start"):
        runtime.update(original, archived_at=None)
    assert original.id != replacement.id
    assert runtime.count("budget_limits", budget_id=budget.id, archived_at=None) == 1
    assert runtime.count("budget_limits", budget_id=budget.id) == 2


def test_daily_and_weekly_limits_can_share_an_active_start(runtime, data):
    user = data.user()
    budget = data.budget(user)
    daily = data.limit(user, budget, start=date(2026, 11, 2), end=date(2026, 11, 3))
    weekly = data.limit(
        user, budget, kind="weekly", start=date(2026, 11, 2), end=date(2026, 11, 9),
        week_start_day=1,
    )
    assert daily.id != weekly.id
    assert runtime.count("budget_limits", budget_id=budget.id, archived_at=None) == 2
    runtime.check_constraints()


@pytest.mark.parametrize("with_limit", [False, True], ids=["null-monthly-scope", "limit-scope"])
def test_unresolved_alert_dedup_read_and_resolution(runtime, data, with_limit):
    user = data.user()
    budget = data.budget(user)
    limit = data.limit(user, budget) if with_limit else None
    alert = data.alert(user, budget, limit=limit)
    with runtime.rejects("23505", constraint="uq_budget_alerts_active_scope"):
        data.alert(user, budget, limit=limit)
    alert = runtime.update(alert, read_at=runtime.clock())
    assert runtime.get(alert)["read_at"] == runtime.clock()
    assert runtime.get(alert)["resolved_at"] is None
    with runtime.rejects("23505", constraint="uq_budget_alerts_active_scope"):
        data.alert(user, budget, limit=limit)

    alert = runtime.update(alert, resolved_at=runtime.clock())
    # Check the lifecycle rule before a replacement could introduce a UNIQUE conflict.
    with runtime.rejects("23514"):
        runtime.update(alert, resolved_at=None)
    replacement = data.alert(user, budget, limit=limit)
    assert alert.id != replacement.id
    assert runtime.get(alert)["resolved_at"] == runtime.clock()
    assert runtime.count(
        "budget_alerts", budget_id=budget.id,
        budget_limit_id=limit.id if limit is not None else None, resolved_at=None,
    ) == 1
    runtime.check_constraints()


def test_alert_types_have_distinct_unresolved_slots_and_thresholds(runtime, data):
    user = data.user()
    budget = data.budget(user)
    for kind, threshold in (("warning", 80), ("over_budget", 100)):
        alert = data.alert(user, budget, kind=kind)
        row = runtime.get(alert)
        assert row["alert_type"] == kind
        assert row["threshold_percent"] == threshold
        assert row["budget_limit_id"] is None
        assert row["resolved_at"] is None
    assert runtime.count("budget_alerts", budget_id=budget.id, resolved_at=None) == 2


@pytest.mark.parametrize("kind,threshold", [("warning", 100), ("over_budget", 80)])
def test_alert_threshold_must_match_type(runtime, data, kind, threshold):
    user = data.user()
    budget = data.budget(user)
    with runtime.rejects("23514", constraint="ck_budget_alerts_threshold"):
        data.alert(user, budget, kind=kind, threshold_percent=threshold)


def test_alert_period_requires_a_later_end(runtime, data):
    user = data.user()
    budget = data.budget(user)
    with runtime.rejects("23514", constraint="ck_budget_alerts_period_order"):
        data.alert(user, budget, period_start=date(2026, 11, 10), period_end=date(2026, 11, 10))


@pytest.mark.parametrize("column,constraint", [
    ("read_at", "ck_budget_alerts_read_order"),
    ("resolved_at", "ck_budget_alerts_resolution_order"),
])
def test_alert_lifecycle_timestamps_cannot_precede_creation(runtime, data, column, constraint):
    user = data.user()
    budget = data.budget(user)
    alert = data.alert(user, budget)
    with runtime.rejects("23514", constraint=constraint):
        runtime.update(alert, **{column: runtime.clock() - timedelta(seconds=1)})
