"""Rollback-only contention. Shared-parent races requiring committed seeds are deferred."""

from queue import Empty, Queue
from threading import Event, Thread
from time import monotonic

import pytest

from .data import Data
from .policy import SafetyError
from .lifecycle import CleanupTimeout, stop_workers


pytestmark = [pytest.mark.integration, pytest.mark.finset_integration, pytest.mark.finset_concurrency]


def test_unique_email_waiter_proceeds_after_other_insert_rolls_back(factory, case):
    """Neither user needs a committed parent; both inserted users must disappear."""
    email = case.email("contended")
    messages = Queue()
    failures = Queue()
    release_first = Event()
    second_inserted = Event()
    deadline = monotonic() + 10

    def remaining():
        duration = min(5, deadline - monotonic())
        if duration <= 0:
            raise AssertionError("The rollback-only contention setup exceeded its shared deadline.")
        return duration

    def worker(first):
        try:
            with factory.rollback("runtime", case) as connection:
                if first:
                    Data(connection).user(email=email)
                    messages.put(("first", connection.backend_pid))
                    # Keep the blocker through the coordinator's deadline plus teardown grace.
                    if not release_first.wait(max(0, deadline - monotonic()) + 5):
                        raise SafetyError("The first rollback worker was not released before its deadline.")
                else:
                    messages.put(("second", connection.backend_pid))
                    Data(connection).user(email=email)
                    second_inserted.set()
        except BaseException as error:
            # Do not move a secret-bearing traceback or raw driver error across threads.
            failures.put((type(error).__name__, getattr(error, "sqlstate", None)))

    first = Thread(target=worker, args=(True,), daemon=True, name="finset-rollback-first")
    second = Thread(target=worker, args=(False,), daemon=True, name="finset-rollback-second")
    workers = (first, second)
    for thread in workers:
        thread.finset_start_requested = False
    try:
        first.finset_start_requested = True
        first.start()
        try:
            label, first_pid = messages.get(timeout=remaining())
        except Empty:
            raise AssertionError("First rollback-only worker did not become ready.") from None
        assert label == "first"
        second.finset_start_requested = True
        second.start()
        try:
            label, second_pid = messages.get(timeout=remaining())
        except Empty:
            raise AssertionError("Second rollback-only worker did not become ready.") from None
        assert label == "second"
        assert first_pid != second_pid
        factory.wait_until_blocked(case, first_pid, second_pid, timeout=remaining())
        assert not second_inserted.is_set()
        release_first.set()
    finally:
        try:
            stop_workers(workers, release_first, lambda budget: factory.cancel_case(case, deadline=budget))
        except CleanupTimeout:
            pytest.exit("Owned workers remain unresolved; supervised run aborted without cleanup writes.", returncode=2)
    assert failures.empty(), "A rollback-only worker failed; raw diagnostics withheld."
    assert second_inserted.is_set()
    # Each factory context independently verified its exact INSERT receipt absent after rollback.
