"""Direct hook fakes: no pytest session, credentials, or database operations."""

from types import SimpleNamespace

import pytest

from .. import policy, safety


@pytest.fixture
def authorized(monkeypatch):
    control = SimpleNamespace(sent=[], secret_registration=lambda values: control.sent.append(tuple(values)))
    config = SimpleNamespace(option=SimpleNamespace(collectonly=False))
    monkeypatch.setattr(safety, "_supervisor", control)
    monkeypatch.setattr(safety, "_config", config)
    monkeypatch.setattr(safety, "_early", True)
    monkeypatch.setattr(safety, "_expected_args", ("synthetic",))
    monkeypatch.setattr(safety, "_selected", True)
    monkeypatch.setattr(safety, "_active_item", "synthetic-test")
    monkeypatch.setattr(safety, "_secrets", ())
    return config, control


def test_secret_registration_uses_only_private_supervisor(authorized):
    _, control = authorized
    safety.register_secrets(["synthetic-sensitive-canary"])
    assert control.sent == [("synthetic-sensitive-canary",)]
    assert safety._secrets == ("synthetic-sensitive-canary",)


def test_collect_only_never_registers_secrets(authorized):
    config, control = authorized
    config.option.collectonly = True
    with pytest.raises(policy.SafetyError):
        safety.register_secrets(["synthetic-sensitive-canary"])
    assert not control.sent


def test_warning_message_and_source_line_are_sanitized_without_dropping_warning(authorized):
    safety.register_secrets(["synthetic-sensitive-canary"])
    warning = SimpleNamespace(message=UserWarning("synthetic-sensitive-canary"),
                              line="synthetic-sensitive-canary", category=UserWarning, lineno=10)
    safety.pytest_warning_recorded(warning, "runtest", "synthetic", None)
    assert warning.message == warning.line == "[REDACTED]"
    assert warning.category is UserWarning and warning.lineno == 10


def test_session_finish_retains_filter_until_worker_output_has_drained(authorized):
    safety.register_secrets(["synthetic-sensitive-canary"])
    hook = safety.pytest_sessionfinish(None, 0)
    next(hook)
    with pytest.raises(StopIteration):
        next(hook)
    assert safety._active_item is None and not safety._selected
    assert safety._secrets == ("synthetic-sensitive-canary",)
    safety.release_secrets()
    assert not safety._secrets


@pytest.mark.parametrize("aborted,pending,retained", [(False, True, False), (True, True, True), (True, False, False)])
def test_teardown_retains_authorization_only_for_pending_emergency_finalizers(authorized, aborted, pending, retained):
    item = SimpleNamespace(session=SimpleNamespace(_setupstate=SimpleNamespace(stack={1: 2} if pending else {})))
    hook = safety.pytest_runtest_teardown(item, None)
    next(hook)
    outcome = SimpleNamespace(excinfo=(KeyboardInterrupt, KeyboardInterrupt(), None) if aborted else None)
    with pytest.raises(StopIteration):
        hook.send(outcome)
    assert (safety._active_item is not None) == retained
