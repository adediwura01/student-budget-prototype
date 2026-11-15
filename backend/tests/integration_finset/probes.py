"""Synthetic, DB-free probes; the worker must install its deny-all unit guard.

These never load configuration, connect, or spawn a process. Deliberate Event
waits are targets for the owned supervisor's deadline, not cleanup mechanisms.
"""

import json
import os
from threading import Event
from urllib.parse import quote, quote_plus

from .supervisor import CONTROL_LIMIT, ControlError, PROBE_NAMES


CANARY = 'synthetic-finset-canary:/p a"ss\\\u00e9'


def _write(fd, data):
    offset = 0
    while offset < len(data):
        try:
            count = os.write(fd, data[offset:])
        except BlockingIOError:
            Event().wait(0.01)
            continue
        except InterruptedError:
            continue
        if count <= 0:
            raise ControlError("Synthetic probe write failed.")
        offset += count


def run(name, control):
    """Return 0 for emit; the other approved probes require parent termination."""
    if type(name) is not str or name not in PROBE_NAMES:
        raise ControlError("Unapproved synthetic probe.")
    if name == "emit":
        control.secret_registration([CANARY])
        value = CANARY.encode("utf-8")
        split = len(value) // 2
        _write(1, b"stdout fd1: " + value[:split])
        _write(2, b"stderr fd2: " + value[:split])
        _write(1, value[split:] + b"\n")
        _write(2, value[split:] + b"\n")
        for variant in (quote(CANARY, safe=""), quote_plus(CANARY),
                        json.dumps(CANARY), repr(value)):
            _write(1, ("stdout variant: " + variant + "\n").encode("utf-8"))
            _write(2, ("stderr variant: " + variant + "\n").encode("utf-8"))
        _write(2, b"stderr connection: postgresql+psycopg://synthetic:withheld@127.0.0.1/synthetic\n")
        return 0
    control.secret_registration([])
    if name == "bad_control":
        _write(1, b"unverified synthetic output must be suppressed\n")
        _write(2, b"unverified synthetic stderr must be suppressed\n")
        _write(control.fileno(), b'{"type":"unexpected","values":[]}\n')
    elif name == "oversize":
        _write(control.fileno(), b'{"type":"secrets","values":["' + b"x" * CONTROL_LIMIT + b'"]}\n')
    Event().wait()
    return 0
