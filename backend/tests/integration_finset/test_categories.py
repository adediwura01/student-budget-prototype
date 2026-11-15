"""Role-specific category DML; cross-role committed visibility is not fabricated."""

from datetime import timedelta
from uuid import uuid4

import pytest

from .policy import VIEW


pytestmark = [pytest.mark.integration, pytest.mark.finset_integration]


def test_custom_normalized_name_reservation_is_per_user_across_types(data, runtime, case):
    first_user, second_user = data.user(), data.user()
    name = case.label("shared")
    original = data.category(first_user, name=name)
    runtime.update(original, archived_at=runtime.clock())
    with runtime.rejects("23505"):
        data.category(first_user, kind="income", name="  " + name.upper() + "  ")
    other = data.category(second_user, kind="income", name=name)
    assert runtime.get(other)["owner_user_id"] == second_user.id


def test_private_category_owner_and_type_are_checked_on_reference(data, runtime):
    first_user, second_user = data.user(), data.user()
    other_expense = data.category(second_user)
    own_income = data.category(first_user, kind="income")
    with runtime.rejects("23514"):
        data.transaction(first_user, kind="expense", category=other_expense)
    with runtime.rejects("23514"):
        data.transaction(first_user, kind="expense", category=own_income)
    with runtime.rejects("23503"):
        data.transaction(first_user, category_id=uuid4())


def test_archived_category_blocks_new_selection_but_not_historical_correction(data, runtime):
    user = data.user()
    category = data.category(user)
    original = data.transaction(user, kind="expense", category=category)
    runtime.update(category, archived_at=runtime.clock())
    with runtime.rejects("23514"):
        data.transaction(user, kind="expense", category=category)
    runtime.update(original, description="synthetic historical correction")
    assert runtime.get(original)["description"] == "synthetic historical correction"


def test_retained_restore_and_new_replacement_differ_for_archived_category(data, runtime):
    user = data.user()
    category = data.category(user)
    plan = data.plan(user, kind="expense", category=category)
    result = data.transaction(user, kind="expense", category=category, plan=plan)
    runtime.update(plan, status="completed", completed_at=runtime.clock())
    runtime.check_constraints()
    now = runtime.clock()
    runtime.update(result, deleted_at=now, recoverable_until=now + timedelta(days=30))
    runtime.update(plan, status="pending", completed_at=None)
    runtime.update(category, archived_at=now)
    runtime.check_constraints()
    runtime.update(result, deleted_at=None, recoverable_until=None)
    runtime.update(plan, status="completed", completed_at=now)
    runtime.check_constraints()
    assert runtime.get(plan)["result_generation"] == 1
    runtime.update(result, deleted_at=now, recoverable_until=now + timedelta(days=30))
    runtime.update(plan, status="pending", completed_at=None)
    runtime.delete(result)
    runtime.check_constraints()
    with runtime.rejects("23514"):
        data.transaction(user, kind="expense", category=category, plan=plan)
    assert runtime.get(plan)["result_generation"] == 1


def test_runtime_cannot_insert_system_category_or_read_maintenance_view(data, runtime):
    with runtime.rejects("42501"):
        data.category(None)
    with runtime.rejects("42501"):
        runtime.read_probe(VIEW)


def test_private_category_bindings_are_acl_protected(data, runtime):
    first, second = data.user(), data.user()
    category = data.category(first)
    with runtime.rejects("42501"):
        runtime.update(category, owner_user_id=second.id)
    with runtime.rejects("42501"):
        runtime.update(category, category_type="income")
    assert runtime.get(category)["owner_user_id"] == first.id


def test_referenced_private_category_cannot_be_deleted(data, runtime):
    user = data.user()
    category = data.category(user)
    transaction = data.transaction(user, kind="expense", category=category)
    with runtime.rejects("23503"):
        runtime.delete(category)
    runtime.delete(transaction)
    assert runtime.delete(category) == 1


def test_maintenance_can_mutate_only_its_approved_view(maintenance, maintenance_data, case):
    category = maintenance_data.system_category()
    assert maintenance.get(category)["id"] == category.id
    maintenance.update(category, name=case.label("renamed"), archived_at=maintenance.clock(), updated_at=maintenance.clock())
    maintenance.update(category, archived_at=None)
    with maintenance.rejects("42501"):
        maintenance.update(category, category_type="income")
    for table in ("categories", "users", "transactions"):
        with maintenance.rejects("42501"):
            maintenance.read_probe(table)
    assert maintenance.delete(category) == 1


def test_system_name_uniqueness_includes_type_and_archived_rows(maintenance, maintenance_data, case):
    name = case.label("system")
    first = maintenance_data.system_category(name=name)
    maintenance.update(first, archived_at=maintenance.clock())
    with maintenance.rejects("23505"):
        maintenance_data.system_category(name=" " + name.upper() + " ")
    second = maintenance_data.system_category(kind="income", name=name)
    assert second.id != first.id
