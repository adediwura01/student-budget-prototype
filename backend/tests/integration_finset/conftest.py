"""Fixtures are lazy: neither collection nor importing this module opens a database."""

import pytest

from .connections import ConnectionFactory
from .data import Data
from .scope import Scope


@pytest.fixture(scope="session")
def factory():
    __tracebackhide__ = True
    instance = ConnectionFactory()
    try:
        instance.check_readiness()
        yield instance
    finally:
        instance.close_all()


@pytest.fixture
def case():
    return Scope()


@pytest.fixture
def runtime(factory, case):
    with factory.rollback("runtime", case) as session:
        yield session


@pytest.fixture
def maintenance(factory, case):
    with factory.rollback("maintenance", case) as session:
        yield session


@pytest.fixture
def migrator(factory, case):
    with factory.rollback("migrator", case, readonly=True) as session:
        yield session


@pytest.fixture
def data(runtime):
    return Data(runtime)


@pytest.fixture
def maintenance_data(maintenance):
    return Data(maintenance)
