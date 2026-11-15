"""Fakes only: capability ordering, resource ownership, deadlines, and owner reset."""

from contextlib import contextmanager
from threading import Event, Lock
from types import SimpleNamespace

import pytest

from .. import connections
from ..lifecycle import CleanupTimeout, Deadline, Handle, Registry, cancel_handle, close_handle, stop_workers
from ..policy import SafetyError
from ..scope import Scope


class Clock:
    def __init__(self):
        self.now = 0

    def __call__(self):
        return self.now


class Connection:
    def __init__(self, pid=1):
        self.info = SimpleNamespace(backend_pid=pid, transaction_status=connections.TransactionStatus.INTRANS)
        self.lock = Lock()
        self.closed = False
        self.cancellations = []
        self.role = "finset_integration_migrator_login"

    def cancel_safe(self, *, timeout):
        self.cancellations.append(timeout)

    def close(self):
        self.closed = True

    @contextmanager
    def transaction(self, *, force_rollback):
        assert force_rollback
        before = self.role
        try:
            yield
        finally:
            self.role = before


def test_unsupported_cancel_gate_precedes_credentials_or_connector(monkeypatch):
    monkeypatch.setattr(connections, "_authorize", lambda: None)
    monkeypatch.setattr(connections.psycopg, "capabilities", SimpleNamespace(has_cancel_safe=lambda: False))
    with pytest.raises(SafetyError, match="libpq 17"):
        connections.ConnectionFactory()


def test_capability_probe_error_is_sanitized(monkeypatch):
    def broken():
        raise RuntimeError("synthetic private capability details")
    monkeypatch.setattr(connections.psycopg, "capabilities", SimpleNamespace(has_cancel_safe=broken))
    with pytest.raises(SafetyError) as result:
        connections.require_bounded_cancellation()
    assert "synthetic private" not in str(result.value)


@pytest.mark.parametrize("runtime,build,supported", [(160000, 180000, False), (180000, 160000, False),
                                                  (170000, 170000, True), (180004, 180004, True)])
def test_cancel_capability_requires_both_runtime_and_wrapper_support(monkeypatch, runtime, build, supported):
    from psycopg import _capabilities
    monkeypatch.setattr(_capabilities.pq, "version", lambda: runtime)
    monkeypatch.setattr(_capabilities.pq, "__build_version__", build)
    monkeypatch.setattr(connections.psycopg, "capabilities", _capabilities.Capabilities())
    if supported:
        assert connections.require_bounded_cancellation() is None
    else:
        with pytest.raises(SafetyError):
            connections.require_bounded_cancellation()


@pytest.mark.parametrize("seconds", [0, -1, True, 121, float("inf"), float("nan")])
def test_deadline_rejects_unbounded_values(seconds):
    with pytest.raises(SafetyError):
        Deadline(seconds)


@pytest.mark.parametrize("cap", [0, -1, True, float("inf")])
def test_cancellation_operation_budget_never_returns_zero_or_unbounded_timeout(cap):
    with pytest.raises(SafetyError):
        Deadline(3).left(cap)


def test_cancel_timeout_is_positive_and_uses_shared_remaining_budget():
    clock = Clock()
    deadline = Deadline(3, clock=clock)
    connection = Connection()
    handle = Handle(connection, "runtime", Scope(), "transaction")
    cancel_handle(handle, deadline)
    clock.now = 2.5
    cancel_handle(handle, deadline)
    assert connection.cancellations == [2, 0.5]
    clock.now = 3
    with pytest.raises(CleanupTimeout):
        cancel_handle(handle, deadline)
    assert connection.cancellations == [2, 0.5]


def test_close_retains_registry_until_confirmation_and_is_idempotent():
    registry = Registry()
    connection = Connection()
    ticket = registry.begin("runtime", Scope(), "transaction")
    handle, allowed = registry.attach(ticket, connection)
    assert allowed and registry.get(connection) is handle
    with pytest.raises(SafetyError):
        registry.remove_closed(handle)
    close_handle(handle, Deadline(2))
    registry.remove_closed(handle)
    assert not registry.snapshot()
    close_handle(handle, Deadline(2))


def test_cancel_preserves_case_ownership_of_verification_and_excludes_other_cases():
    registry = Registry()
    case, other = Scope(), Scope()
    first = Connection(1)
    old, _ = registry.attach(registry.begin("runtime", case, "transaction"), first)
    first.close()
    registry.remove_closed(old)
    verification = Connection(2)
    current, _ = registry.attach(registry.begin("runtime", case, "verification"), verification)
    unrelated, _ = registry.attach(registry.begin("runtime", other, "verification"), Connection(3))
    assert registry.cancel(case) == (current,)
    assert unrelated not in registry.snapshot(case)
    with pytest.raises(SafetyError):
        registry.begin("runtime", case, "verification")


def test_factory_case_cancel_includes_verification_without_registry_lock_during_io(monkeypatch):
    monkeypatch.setattr(connections, "require_bounded_cancellation", lambda: None)
    factory = object.__new__(connections.ConnectionFactory)
    factory._registry = Registry()
    case = Scope()
    connection = Connection()
    original = connection.cancel_safe
    def cancel(*, timeout):
        assert not factory._registry.lock._is_owned()
        original(timeout=timeout)
    connection.cancel_safe = cancel
    factory._registry.attach(factory._registry.begin("runtime", case, "verification"), connection)
    factory.cancel_case(case)
    assert connection.cancellations and connection.cancellations[0] > 0


def test_late_open_is_tracked_but_never_allowed_after_shutdown():
    registry = Registry()
    ticket = registry.begin("runtime", Scope(), "transaction")
    _, opening = registry.shutdown()
    assert opening
    handle, allowed = registry.attach(ticket, Connection())
    assert not allowed and registry.snapshot() == (handle,)
    with pytest.raises(SafetyError):
        registry.begin("runtime", None, "readiness")


class Worker:
    def __init__(self, *, alive=True, interrupt=False, ident=1):
        self.alive = alive
        self.interrupt = interrupt
        self.ident = ident
        self.finset_start_requested = True
        self.joins = []

    def join(self, *, timeout):
        self.joins.append(timeout)
        if self.interrupt:
            self.interrupt = False
            raise KeyboardInterrupt

    def is_alive(self):
        return self.alive


def test_join_interrupt_still_cancels_every_owned_worker():
    workers = [Worker(interrupt=True), Worker()]
    releases = Event()
    calls = []
    def cancel(deadline):
        calls.append(deadline)
        for worker in workers:
            worker.alive = False
    with pytest.raises(KeyboardInterrupt):
        stop_workers(workers, releases, cancel)
    assert releases.is_set() and len(calls) == 1
    assert all(len(worker.joins) == 2 for worker in workers)


def test_uncertain_startup_is_not_reported_as_clean():
    worker = Worker(alive=False, ident=None)
    with pytest.raises(CleanupTimeout, match="startup"):
        stop_workers([worker], Event(), lambda deadline: None)


def test_owner_flag_clears_and_session_retires_when_reset_fails(monkeypatch):
    monkeypatch.setattr(connections, "_authorize", lambda: None)
    connection = Connection()
    session = connections.Session(SimpleNamespace(_closing=False), connection, "migrator", Scope(), True)
    calls = []
    def execute(conn, statement, params=()):
        calls.append(statement)
        if statement == "SET LOCAL ROLE finset_owner":
            conn.role = "finset_owner"
        elif statement == "RESET ROLE":
            raise SafetyError("synthetic reset failure")
    monkeypatch.setattr(connections, "query", execute)
    monkeypatch.setattr(connections.Session, "identity", lambda self: {"current_user": self._conn.role})
    with pytest.raises(SafetyError, match="reset failure"):
        with session.owner():
            assert session._owner_active and connection.role == "finset_owner"
    assert not session._owner_active and session._role_broken
    assert connection.role == "finset_integration_migrator_login"
    assert calls.count("RESET ROLE") == 1
    with pytest.raises(SafetyError):
        session._check()


def test_owner_session_retires_even_when_savepoint_rollback_fails(monkeypatch):
    monkeypatch.setattr(connections, "_authorize", lambda: None)
    connection = Connection()
    @contextmanager
    def broken_transaction(*, force_rollback):
        assert force_rollback
        yield
        raise SafetyError("synthetic rollback failure")
    connection.transaction = broken_transaction
    session = connections.Session(SimpleNamespace(_closing=False), connection, "migrator", Scope(), True)
    def execute(conn, statement, params=()):
        if statement == "SET LOCAL ROLE finset_owner":
            conn.role = "finset_owner"
        elif statement == "RESET ROLE":
            conn.role = "finset_integration_migrator_login"
    monkeypatch.setattr(connections, "query", execute)
    monkeypatch.setattr(connections.Session, "identity", lambda self: {"current_user": self._conn.role})
    with pytest.raises(SafetyError, match="rollback failure"):
        with session.owner():
            assert session._owner_active
    assert not session._owner_active and session._role_broken and session.readonly
