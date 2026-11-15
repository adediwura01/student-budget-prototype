"""Cooperative deadlines and owned resources. Native hard stops belong to the supervisor."""

from contextlib import contextmanager
from dataclasses import dataclass, field
from threading import RLock
from time import monotonic

from .policy import SafetyError


class CleanupTimeout(SafetyError):
    pass


class Deadline:
    def __init__(self, seconds, *, clock=monotonic):
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not 0 < seconds <= 120:
            raise SafetyError("A positive, bounded deadline is required.")
        self.clock = clock
        self.expires = clock() + seconds

    def left(self, cap=None):
        if cap is not None and (isinstance(cap, bool) or not isinstance(cap, (int, float)) or not 0 < cap <= 120):
            raise SafetyError("An operation timeout must be positive and bounded; zero disables cancellation bounds.")
        remaining = self.expires - self.clock()
        if remaining <= 0:
            raise CleanupTimeout("The cooperative cleanup deadline expired; verification is incomplete.")
        return min(remaining, cap) if cap is not None else remaining

    def wait(self, cap=None):
        return max(0, min(self.expires - self.clock(), cap if cap is not None else 120))


@dataclass(eq=False, repr=False)
class Handle:
    connection: object
    role: str
    case: object
    phase: str
    lock: object = field(default_factory=RLock)

    def __repr__(self):
        return f"<OwnedConnection role={self.role} phase={self.phase}>"


class Registry:
    def __init__(self):
        self.lock = RLock()
        self.handles = {}
        self.opening = {}
        self.cancelled = set()
        self.closing = False

    def begin(self, role, case, phase):
        with self.lock:
            if self.closing or case is not None and id(case) in self.cancelled:
                raise SafetyError("Closing resources cannot accept new connection attempts.")
            ticket = object()
            self.opening[ticket] = (role, case, phase)
            return ticket

    def attach(self, ticket, connection):
        with self.lock:
            role, case, phase = self.opening.pop(ticket)
            handle = Handle(connection, role, case, phase)
            self.handles[id(connection)] = handle
            allowed = not self.closing and (case is None or id(case) not in self.cancelled)
            return handle, allowed

    def finish_open(self, ticket):
        with self.lock:
            self.opening.pop(ticket, None)

    def get(self, connection):
        with self.lock:
            handle = self.handles.get(id(connection))
            if handle is None or handle.connection is not connection:
                raise SafetyError("An exact owned connection handle is required.")
            return handle

    def remove_closed(self, handle):
        with self.lock:
            if not handle.connection.closed:
                raise SafetyError("An unclosed handle cannot be removed from the registry.")
            self.handles.pop(id(handle.connection), None)

    def snapshot(self, case=None):
        with self.lock:
            return tuple(handle for handle in self.handles.values()
                         if case is None or handle.case is case)

    def cancel(self, case):
        with self.lock:
            self.cancelled.add(id(case))
            return self.snapshot(case)

    def shutdown(self):
        with self.lock:
            self.closing = True
            return self.snapshot(), bool(self.opening)


@contextmanager
def bounded_lock(lock, deadline, cap=3):
    if not lock.acquire(timeout=deadline.left(cap)):
        raise CleanupTimeout("An owned resource could not be locked before the deadline.")
    try:
        yield
    finally:
        lock.release()


def cancel_handle(handle, deadline):
    """No registry mutex is held while the verified modern adapter performs I/O."""
    with bounded_lock(handle.lock, deadline):
        if not handle.connection.closed:
            handle.connection.cancel_safe(timeout=deadline.left(2))


def close_handle(handle, deadline):
    with bounded_lock(handle.lock, deadline):
        with bounded_lock(handle.connection.lock, deadline):
            handle.connection.close()
        if not handle.connection.closed:
            raise SafetyError("Owned connection closure was not confirmed.")


def stop_workers(workers, release, cancel, *, budget=8, clock=monotonic):
    """Track objects before start; continue bounded cleanup after repeated interrupts."""
    deadline = Deadline(budget, clock=clock)
    interrupted = False
    release.set()
    for worker in workers:
        try:
            if worker.ident is not None:
                worker.join(timeout=deadline.wait(2))
        except KeyboardInterrupt:
            interrupted = True
    survivors = [worker for worker in workers if worker.is_alive()]
    if survivors:
        try:
            cancel(deadline)
        except KeyboardInterrupt:
            interrupted = True
        except SafetyError:
            pass
        finally:
            for worker in survivors:
                try:
                    worker.join(timeout=deadline.wait(2))
                except KeyboardInterrupt:
                    interrupted = True
    alive = any(worker.is_alive() for worker in workers)
    # Thread.start() may be interrupted after native startup but before ident is visible.
    uncertain = any(getattr(worker, "finset_start_requested", False)
                    and worker.ident is None for worker in workers)
    if alive or uncertain:
        raise CleanupTimeout("Owned workers or startup remain unresolved; the supervisor must abort the child.")
    if interrupted:
        raise KeyboardInterrupt
