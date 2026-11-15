"""Preloaded pytest guard. A marker alone can never authorize a connection."""

import os
from pathlib import Path
from threading import RLock

import psycopg
import pytest
from sqlalchemy.engine import Engine

# Import first so the private factory captures its connector before public APIs are blocked.
from . import connections
from .policy import SUITE, SafetyError, redact_report, validate_selection


_lock = RLock()
_expected_args = None
_early = False
_config = None
_selected = False
_active_item = None
_secrets = ()
_supervisor = None


def _blocked_connection(*args, **kwargs):
    __tracebackhide__ = True
    raise SafetyError("Direct database connections are blocked; use the validated FinSet factory.")


# These remain blocked for the entire process, including collection and session fixtures.
psycopg.connect = _blocked_connection
psycopg.Connection.connect = classmethod(_blocked_connection)
psycopg.AsyncConnection.connect = classmethod(_blocked_connection)
Engine.connect = _blocked_connection
Engine.raw_connection = _blocked_connection


def authorize_launcher(args):
    global _expected_args
    if _expected_args is not None:
        raise SafetyError("A FinSet test process may not be reused for another run.")
    _expected_args = tuple(args)


def attach_supervisor(control):
    global _supervisor
    if _supervisor is not None or _expected_args is not None:
        raise SafetyError("A test process may attach to only one owned supervisor.")
    _supervisor = control


def was_preloaded(config):
    return _early and _config is config and _expected_args is not None


def execution_allowed():
    with _lock:
        return bool(_supervisor is not None and _selected and _active_item is not None and _config is not None
                    and not _config.option.collectonly and was_preloaded(_config))


def register_secrets(values):
    global _secrets
    if not execution_allowed():
        raise SafetyError("Credentials may not be loaded during collection.")
    _secrets = tuple(values)
    _supervisor.secret_registration(list(_secrets))


def release_secrets():
    global _secrets
    _secrets = ()


def pytest_addoption(parser):
    group = parser.getgroup("finset integration")
    group.addoption("--run-finset-integration", action="store_true", default=False,
                    help="Explicitly opt into the guarded FinSet-only profile.")
    group.addoption("--allow-finset-commits", action="store_true", default=False,
                    help="Reserved for a future reviewed committed fixture profile; rejected in Stage A.")


@pytest.hookimpl(tryfirst=True)
def pytest_load_initial_conftests(early_config, parser, args):
    global _early
    if (_expected_args is None or tuple(args) != _expected_args
            or os.environ.get("PYTEST_DISABLE_PLUGIN_AUTOLOAD") != "1"
            or os.environ.get("PYTEST_ADDOPTS") or os.environ.get("PYTEST_PLUGINS")):
        raise pytest.UsageError("Use the controlled python -m tests.integration_finset launcher; ambient options/plugins are prohibited.")
    _early = True


def pytest_configure(config):
    global _config
    if not _early or _expected_args is None or _supervisor is None:
        raise pytest.UsageError("The FinSet guard must be preloaded before initial conftest/test imports.")
    _config = config
    if (config.getoption("showlocals", default=False)
            or config.getoption("xmlpath", default=None)
            or config.getoption("log_file", default=None)
            or config.getoption("capture", default="fd") not in ("fd", "sys")
            or config.getoption("continue_on_collection_errors", default=False)
            or config.getini("log_cli")
            or config.pluginmanager.list_plugin_distinfo()):
        raise pytest.UsageError("Unsafe reporting, capture, collection, or third-party plugin configuration.")
    if not config.getoption("run_finset_integration") or config.getoption("allow_finset_commits"):
        raise pytest.UsageError("Stage A requires explicit opt-in and prohibits committed execution.")


@pytest.hookimpl(tryfirst=True)
def pytest_pycollect_makemodule(module_path, parent):
    if not Path(module_path).resolve().is_relative_to(SUITE):
        raise pytest.UsageError("The dedicated profile cannot import legacy or unintended test modules.")


def pytest_collection_finish(session):
    global _selected
    if session.testsfailed:
        raise pytest.UsageError("Collection errors prevent all FinSet database access.")
    items = [(item.path, {marker.name for marker in item.iter_markers()}) for item in session.items]
    parameters = {name for item in session.items for name in getattr(getattr(item, "callspec", None), "params", {})}
    try:
        validate_selection(items, opted_in=session.config.getoption("run_finset_integration"),
                           allow_commits=session.config.getoption("allow_finset_commits"),
                           parameter_names=parameters)
    except SafetyError as error:
        raise pytest.UsageError(str(error)) from None
    _selected = True


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    global _active_item
    if not _selected or not was_preloaded(item.config):
        raise pytest.UsageError("The dedicated collection has not passed its safety gate.")
    try:
        validate_selection([(item.path, {marker.name for marker in item.iter_markers()})],
                           opted_in=True, allow_commits=item.config.getoption("allow_finset_commits"),
                           parameter_names=getattr(getattr(item, "callspec", None), "params", {}))
    except SafetyError as error:
        raise pytest.UsageError(str(error)) from None
    with _lock:
        _active_item = item.nodeid


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_teardown(item, nextitem):
    global _active_item
    outcome = None
    try:
        outcome = yield
    finally:
        state = getattr(item.session, "_setupstate", None)
        pending_finalizers = bool(getattr(state, "stack", {}))
        aborted = outcome is None or outcome.excinfo is not None
        if not aborted or not pending_finalizers:
            with _lock:
                _active_item = None


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    redact_report(report, _secrets)


@pytest.hookimpl(tryfirst=True)
def pytest_collectreport(report):
    redact_report(report, _secrets)


@pytest.hookimpl(tryfirst=True)
def pytest_warning_recorded(warning_message, when, nodeid, location):
    from .policy import redact
    warning_message.message = redact(str(warning_message.message), _secrets)
    if warning_message.line:
        warning_message.line = redact(warning_message.line, _secrets)


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_sessionfinish(session, exitstatus):
    global _active_item, _selected
    try:
        yield
    finally:
        # Pytest's emergency fixture finalization must still be authorized/redacted.
        _active_item = None
        _selected = False
