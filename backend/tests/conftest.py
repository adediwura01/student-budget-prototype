"""Block direct connections from collection onward; live tests need the guarded factory."""

import sys

import psycopg
import pytest
from sqlalchemy.engine import Engine


def forbidden_connection(*args, **kwargs):
    __tracebackhide__ = True
    pytest.fail("Direct database connections are forbidden; only the preloaded FinSet factory is permitted.")


# Function-scoped fixtures run too late to protect collection or session setup.
# The dedicated launcher captures its private connector before importing this file.
psycopg.connect = forbidden_connection
psycopg.Connection.connect = classmethod(forbidden_connection)
psycopg.AsyncConnection.connect = classmethod(forbidden_connection)
Engine.connect = forbidden_connection
Engine.raw_connection = forbidden_connection


def pytest_collection_finish(session):
    """A generic integration marker must not reach either database profile."""
    for item in session.items:
        if item.get_closest_marker("integration") is None:
            continue
        guard = sys.modules.get("tests.integration_finset.safety")
        if (item.get_closest_marker("finset_integration") is None
                or guard is None or not guard.was_preloaded(session.config)):
            raise pytest.UsageError(
                "Legacy/broad integration selection is disabled. Use the dedicated FinSet launcher; "
                "finset_test must not be contacted by this profile."
            )


@pytest.fixture(autouse=True)
def block_database_connections_in_unit_tests(request, monkeypatch):
    if request.node.get_closest_marker("integration") is not None:
        guard = sys.modules.get("tests.integration_finset.safety")
        if (request.node.get_closest_marker("finset_integration") is None
                or guard is None or not guard.execution_allowed()):
            pytest.fail("Integration execution did not pass the dedicated FinSet safety gate.")
        return

    monkeypatch.setattr(Engine, "connect", forbidden_connection)
    monkeypatch.setattr(Engine, "raw_connection", forbidden_connection)
    monkeypatch.setattr(psycopg, "connect", forbidden_connection)
    monkeypatch.setattr(psycopg.Connection, "connect", classmethod(forbidden_connection))
    monkeypatch.setattr(psycopg.AsyncConnection, "connect", classmethod(forbidden_connection))
