"""Preloaded network/credential canary for explicitly selected Stage B tests."""

import os
from collections import Counter
from pathlib import Path
import socket
import sys

import psycopg
import pytest
from sqlalchemy.engine import Engine

from .. import policy


ROOT = Path(__file__).resolve().parent
LEGACY_SAFETY = policy.BACKEND / "tests" / "test_integration_safety.py"
ATTEMPTS = {"database": 0, "credentials": 0, "readiness": 0, "network": 0}
_installed = False


def forbidden_database(*args, **kwargs):
    __tracebackhide__ = True
    ATTEMPTS["database"] += 1
    raise policy.SafetyError("Stage B forbids every real database connection.")


def forbidden_credentials(*args, **kwargs):
    __tracebackhide__ = True
    ATTEMPTS["credentials"] += 1
    raise policy.SafetyError("Stage B cannot load real integration credentials.")


def forbidden_readiness(*args, **kwargs):
    __tracebackhide__ = True
    ATTEMPTS["readiness"] += 1
    raise policy.SafetyError("Stage B cannot execute live readiness.")


def forbidden_network(*args, **kwargs):
    __tracebackhide__ = True
    ATTEMPTS["network"] += 1
    raise policy.SafetyError("Stage B prohibits network connections.")


def install():
    global _installed
    if _installed:
        return
    _installed = True
    psycopg.connect = forbidden_database
    psycopg.Connection.connect = classmethod(forbidden_database)
    psycopg.AsyncConnection.connect = classmethod(forbidden_database)
    Engine.connect = forbidden_database
    Engine.raw_connection = forbidden_database
    socket.socket.connect = forbidden_network
    socket.socket.connect_ex = forbidden_network
    socket.create_connection = forbidden_network
    policy.load_credentials = forbidden_credentials
    # Capture the private connector only after all public connector APIs are denied.
    from .. import connections, readiness
    connections._CONNECT = forbidden_database
    connections.load_credentials = forbidden_credentials
    readiness.check_readiness = forbidden_readiness
    connections.ConnectionFactory.check_readiness = forbidden_readiness
    secret_paths = {os.path.normcase(str(policy.BACKEND / name)) for name in (".env", ".env.integration")}

    def audit(event, args):
        if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
            path = os.path.normcase(os.path.abspath(os.fsdecode(args[0])))
            if path in secret_paths:
                forbidden_credentials()
        elif event == "socket.connect":
            forbidden_network()

    sys.addaudithook(audit)


install()


def pytest_collection_finish(session):
    if not session.items:
        raise pytest.UsageError("Stage B must select at least one DB-free test.")
    for item in session.items:
        path = Path(item.path).resolve()
        if path != LEGACY_SAFETY.resolve() and not path.is_relative_to(ROOT):
            raise pytest.UsageError("Stage B cannot collect tests outside the exact unit-test allowlist.")
        if item.get_closest_marker("integration") or item.get_closest_marker("finset_integration"):
            raise pytest.UsageError("Live integration markers are forbidden in Stage B.")


def pytest_terminal_summary(terminalreporter):
    counts = Counter(report.nodeid.split("::", 1)[0] or Path(report.location[0]).name
                     for report in terminalreporter.stats.get("passed", []))
    terminalreporter.write_sep("=", "Stage B DB-free results")
    for path, count in sorted(counts.items()):
        terminalreporter.write_line(f"{path}: {count} passed")
    terminalreporter.write_line("Real-resource canary intercepts: " + str(ATTEMPTS))
