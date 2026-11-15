"""Permission rejection is distinct from execution of an unreachable guard branch."""

from uuid import uuid4

import pytest

from .policy import DATABASE, ROLES, TABLES


pytestmark = [pytest.mark.integration, pytest.mark.finset_integration]


@pytest.mark.parametrize("target", ["finset_owner", "finset_migrator", "finset_maintenance"])
def test_runtime_cannot_assume_other_roles(runtime, target):
    with runtime.rejects("42501"):
        runtime.role_probe(target)
    identity = runtime.identity()
    assert identity["database"] == DATABASE
    assert identity["current_user"] == ROLES["runtime"][1]


@pytest.mark.parametrize("target", ["finset_owner", "finset_migrator", "finset_runtime"])
def test_maintenance_cannot_assume_other_roles(maintenance, target):
    with maintenance.rejects("42501"):
        maintenance.role_probe(target)
    assert maintenance.identity()["current_user"] == ROLES["maintenance"][1]


def test_migrator_owner_assumption_is_explicit_read_only_and_resets(migrator):
    before = migrator.identity()
    assert before["current_user"] == ROLES["migrator"][1]
    with migrator.owner():
        owner = migrator.identity()
        assert owner["session_user"] == ROLES["migrator"][1]
        assert owner["current_user"] == "finset_owner"
        assert owner["read_only"] == "on"
    assert migrator.identity()["current_user"] == before["current_user"]


@pytest.mark.parametrize("target", ["finset_runtime", "finset_maintenance"])
def test_ordinary_migrator_cannot_assume_application_roles(migrator, target):
    with migrator.rejects("42501"):
        migrator.role_probe(target)


def test_runtime_cannot_directly_call_allocator_or_write_counter(data, runtime):
    user = data.user()
    plan = data.plan(user)
    with runtime.rejects("42501"):
        runtime.function_probe("finset_allocate_plan_result")
    with runtime.rejects("42501"):
        runtime.update(plan, result_generation=1)
    with runtime.rejects("42501"):
        data.plan(user, result_generation=0)
    assert runtime.get(plan)["result_generation"] == 0


def record_for_table(data, table):
    user = data.user()
    if table == "users":
        return user
    if table == "categories":
        return data.category(user)
    if table == "plans":
        return data.plan(user)
    if table == "transactions":
        return data.transaction(user)
    if table == "login_sessions":
        return data.login_session(user)
    if table == "auth_tokens":
        return data.token(user)
    budget = data.budget(user)
    if table == "monthly_budgets":
        return budget
    if table == "budget_limits":
        return data.limit(user, budget)
    return data.alert(user, budget)


@pytest.mark.parametrize("table", TABLES)
def test_runtime_identity_updates_are_denied_before_immutable_trigger(data, runtime, table):
    record = record_for_table(data, table)
    with runtime.rejects("42501"):
        runtime.update(record, id=uuid4())
    assert runtime.get(record)["id"] == record.id
