"""Owned-reference and deletion constraints, not per-student SQL isolation."""

import pytest


pytestmark = [pytest.mark.integration, pytest.mark.finset_integration]


def test_plan_result_requires_the_plan_owner(runtime, data):
    owner = data.user()
    other = data.user()
    plan = data.plan(owner)
    # The BEFORE INSERT result-preparation trigger may reject before the FK runs.
    with runtime.rejects("23503"):
        data.transaction(other, plan_id=plan.id, category_id=None)
    assert runtime.count("transactions", user_id=other.id) == 0

    result = data.transaction(owner, plan_id=plan.id, category_id=None)
    runtime.update(plan, status="completed", completed_at=runtime.clock())
    runtime.check_constraints()
    assert runtime.get(result)["user_id"] == owner.id
    assert runtime.get(result)["plan_id"] == plan.id
    assert runtime.get(plan)["status"] == "completed"


def test_plan_result_requires_the_plan_type(runtime, data):
    user = data.user()
    category = data.category(user)
    plan = data.plan(user, kind="expense", category=category)
    with runtime.rejects("23503"):
        data.transaction(user, kind="income", plan_id=plan.id, category_id=None)
    assert runtime.get(plan)["status"] == "pending"
    assert runtime.count("transactions", user_id=user.id) == 0


@pytest.mark.parametrize("builder", ["plan", "transaction", "budget"])
@pytest.mark.parametrize("violation", ["owner", "type", "archived"])
def test_category_reference_guards(runtime, data, builder, violation):
    user = data.user()
    category_owner = data.user() if violation == "owner" else user
    category = data.category(
        category_owner, kind="income" if violation == "type" else "expense",
    )
    if violation == "archived":
        category = runtime.update(category, archived_at=runtime.clock())
    options = {"category": category}
    if builder != "budget":
        options["kind"] = "expense"
    # Each case has exactly one bad selection property and otherwise valid parents.
    with runtime.rejects("23514"):
        getattr(data, builder)(user, **options)


@pytest.mark.parametrize("builder,column", [
    ("plan", "expected_amount_kobo"),
    ("transaction", "amount_kobo"),
    ("budget", "allocation_kobo"),
])
def test_archiving_category_preserves_existing_references(runtime, data, builder, column):
    user = data.user()
    category = data.category(user)
    options = {"category": category}
    if builder != "budget":
        options["kind"] = "expense"
    record = getattr(data, builder)(user, **options)
    runtime.update(category, archived_at=runtime.clock())
    record = runtime.update(record, **{column: 2000})
    runtime.check_constraints()
    assert runtime.get(record)["category_id"] == category.id
    assert runtime.get(record)[column] == 2000


@pytest.mark.parametrize("builder,constraint", [
    ("limit", "fk_budget_limits_owned_budget"),
    ("alert", "fk_budget_alerts_owned_budget"),
])
def test_budget_children_require_an_owned_budget(runtime, data, builder, constraint):
    owner = data.user()
    other = data.user()
    budget = data.budget(owner)
    # An alert has a NULL limit, so only its owned-budget FK is invalid.
    with runtime.rejects("23503", constraint=constraint):
        getattr(data, builder)(other, budget)


@pytest.mark.parametrize("foreign_owner", [False, True], ids=["other-budget", "other-owner"])
def test_alert_limit_must_belong_to_its_owned_budget(runtime, data, foreign_owner):
    user = data.user()
    budget = data.budget(user)
    limit_owner = data.user() if foreign_owner else user
    other_budget = data.budget(limit_owner)
    other_limit = data.limit(limit_owner, other_budget)
    # The alert's own user/budget pair is valid; only the owned-limit FK fails.
    with runtime.rejects("23503", constraint="fk_budget_alerts_owned_limit"):
        data.alert(user, budget, budget_limit_id=other_limit.id)


@pytest.mark.parametrize("parent_kind,child_kind,constraint", [
    ("user", "transaction", "fk_transactions_user"),
    ("user", "plan", "fk_plans_user"),
    ("user", "category", "fk_categories_owner"),
    ("category", "transaction", "fk_transactions_category"),
    ("category", "plan", "fk_plans_category"),
    ("category", "budget", "fk_monthly_budgets_category"),
    ("budget", "limit", "fk_budget_limits_owned_budget"),
    ("budget", "alert", "fk_budget_alerts_owned_budget"),
    ("limit", "alert", "fk_budget_alerts_owned_limit"),
])
def test_referenced_parent_delete_is_restricted(
    runtime, data, parent_kind, child_kind, constraint,
):
    user = data.user()
    if parent_kind == "user":
        parent = user
        child = getattr(data, child_kind)(user)
    elif parent_kind == "category":
        parent = data.category(user)
        options = {"category": parent}
        if child_kind != "budget":
            options["kind"] = "expense"
        child = getattr(data, child_kind)(user, **options)
    elif parent_kind == "budget":
        parent = data.budget(user)
        child = getattr(data, child_kind)(user, parent)
    else:
        budget = data.budget(user)
        parent = data.limit(user, budget)
        child = data.alert(user, budget, limit=parent)

    with runtime.rejects("23503", constraint=constraint):
        runtime.delete(parent)
    assert runtime.get(parent) is not None
    assert runtime.get(child) is not None
    assert runtime.delete(child) == 1
    assert runtime.delete(parent) == 1
    assert runtime.get(child) is None
    assert runtime.get(parent) is None
    runtime.check_constraints()
