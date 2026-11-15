"""Real trigger paths exercised by ordinary runtime DML, always rolled back."""

from datetime import date, timedelta

import pytest


pytestmark = [pytest.mark.integration, pytest.mark.finset_integration]


def completed_pair(data, runtime):
    user = data.user()
    plan = data.plan(user)
    result = data.transaction(user, plan=plan)
    runtime.update(plan, status="completed", completed_at=runtime.clock())
    runtime.check_constraints()
    return user, plan, result


def undo(runtime, plan, result):
    now = runtime.clock()
    runtime.update(result, deleted_at=now, recoverable_until=now + timedelta(days=30))
    runtime.update(plan, status="pending", completed_at=None)
    runtime.check_constraints()


def test_result_insert_allocates_only_generation_then_explicit_completion(data, runtime):
    user = data.user()
    plan = data.plan(user, expected_amount=1000)
    before = runtime.get(plan)
    assert (before["status"], before["result_generation"]) == ("pending", 0)
    result = data.transaction(user, plan=plan, amount=1750, transaction_date=date(2026, 11, 14))
    allocated = runtime.get(plan)
    assert allocated["result_generation"] == 1
    assert allocated["status"] == "pending"
    assert allocated["version"] == before["version"]
    assert allocated["updated_at"] == before["updated_at"]
    runtime.update(plan, status="completed", completed_at=runtime.clock(), version=2)
    runtime.check_constraints()
    assert runtime.get(result)["amount_kobo"] == 1750
    assert runtime.get(plan)["expected_amount_kobo"] == 1000


def test_completion_without_timestamp_is_an_immediate_row_failure(data, runtime):
    plan = data.plan(data.user())
    with runtime.rejects("23514", "ck_plans_completion_state"):
        runtime.update(plan, status="completed", completed_at=None)
    assert runtime.get(plan)["status"] == "pending"


def test_completed_without_result_fails_deferred_final_state(data, runtime):
    plan = data.plan(data.user())
    with runtime.rejects("23514", "finset_plan_result_final_state"):
        runtime.update(plan, status="completed", completed_at=runtime.clock())
        runtime.check_constraints()
    assert (runtime.get(plan)["status"], runtime.get(plan)["result_generation"]) == ("pending", 0)


def test_active_result_with_pending_plan_rolls_back_result_and_generation(data, runtime):
    user = data.user()
    plan = data.plan(user)
    with runtime.rejects("23514", "finset_plan_result_final_state"):
        data.transaction(user, plan=plan)
        assert runtime.get(plan)["result_generation"] == 1
        runtime.check_constraints()
    assert runtime.get(plan)["result_generation"] == 0
    assert runtime.count("transactions", plan_id=plan.id) == 0


def test_later_statement_failure_rolls_back_the_entire_recording_attempt(data, runtime):
    user = data.user()
    plan = data.plan(user)
    with runtime.rejects("23514", "ck_plans_completion_state"):
        data.transaction(user, plan=plan)
        runtime.update(plan, status="completed", completed_at=None)
    assert runtime.get(plan)["result_generation"] == 0
    assert runtime.count("transactions", plan_id=plan.id) == 0


def test_completed_plan_rejects_duplicate_at_eligibility_guard(data, runtime):
    user, plan, result = completed_pair(data, runtime)
    with runtime.rejects("23514"):
        data.transaction(user, plan=plan)
    assert runtime.get(plan)["result_generation"] == 1
    assert runtime.rows("transactions", plan_id=plan.id)[0]["id"] == result.id


@pytest.mark.parametrize("ignore_conflict", [False, True])
def test_retained_deleted_result_reserves_slot_even_with_do_nothing(data, runtime, ignore_conflict):
    user, plan, result = completed_pair(data, runtime)
    undo(runtime, plan, result)
    with runtime.rejects("23505"):
        data.transaction(user, plan=plan, ignore_conflict=ignore_conflict)
    assert runtime.get(plan)["result_generation"] == 1
    assert runtime.count("transactions", plan_id=plan.id) == 1


def test_repeated_undo_and_restore_reuses_uuid_without_consuming_generations(data, runtime):
    _, plan, result = completed_pair(data, runtime)
    for _ in range(2):
        undo(runtime, plan, result)
        assert runtime.get(result)["deleted_at"] is not None
        runtime.update(result, deleted_at=None, recoverable_until=None)
        runtime.update(plan, status="completed", completed_at=runtime.clock())
        runtime.check_constraints()
        assert runtime.get(result)["id"] == result.id
        assert runtime.get(plan)["result_generation"] == 1


def test_purge_allows_one_replacement_but_never_a_third_allocation(data, runtime):
    user, plan, first = completed_pair(data, runtime)
    undo(runtime, plan, first)
    assert runtime.delete(first) == 1
    runtime.check_constraints()
    assert runtime.get(plan)["result_generation"] == 1
    second = data.transaction(user, plan=plan)
    assert second.id != first.id
    runtime.update(plan, status="completed", completed_at=runtime.clock())
    runtime.check_constraints()
    assert runtime.get(plan)["result_generation"] == 2
    undo(runtime, plan, second)
    runtime.delete(second)
    runtime.check_constraints()
    with runtime.rejects("23514"):
        data.transaction(user, plan=plan)
    assert runtime.get(plan)["result_generation"] == 2
    assert runtime.count("transactions", plan_id=plan.id) == 0


def test_active_result_cannot_be_deleted_without_reconciling_its_plan(data, runtime):
    _, plan, result = completed_pair(data, runtime)
    with runtime.rejects("23514", "finset_plan_result_final_state"):
        runtime.delete(result)
        runtime.check_constraints()
    assert runtime.get(result) is not None
    assert runtime.get(plan)["status"] == "completed"


def test_parent_delete_is_restricted_but_child_then_parent_is_valid(data, runtime):
    _, plan, result = completed_pair(data, runtime)
    with runtime.rejects("23503"):
        runtime.delete(plan)
    runtime.delete(result)
    runtime.delete(plan)
    runtime.check_constraints()
    assert runtime.get(result) is None
    assert runtime.get(plan) is None


def test_pending_cancelled_reopening_is_not_falsely_treated_as_irreversible(data, runtime):
    plan = data.plan(data.user())
    runtime.update(plan, status="cancelled", completed_at=None)
    runtime.check_constraints()
    runtime.update(plan, status="pending", completed_at=None)
    runtime.check_constraints()
    assert runtime.get(plan)["result_generation"] == 0


def test_existing_deleted_window_cannot_be_extended(data, runtime):
    _, plan, result = completed_pair(data, runtime)
    undo(runtime, plan, result)
    before = runtime.get(result)
    with runtime.rejects("23514"):
        runtime.update(result, recoverable_until=before["recoverable_until"] + timedelta(days=1))
    assert runtime.get(result)["recoverable_until"] == before["recoverable_until"]
