"""DB-free regressions for the pure FinSet policy and receipt registry.

Every connection string is synthetic. No provisioning file is loaded, and these
tests have no integration marker, so the normal database blocker stays active.
"""

from dataclasses import replace
from types import SimpleNamespace
from uuid import UUID

import pytest

from tests.integration_finset import policy, scope


CREDENTIAL_KEYS = {
    "runtime": "FINSET_INTEGRATION_RUNTIME_DATABASE_URL",
    "migrator": "FINSET_INTEGRATION_MIGRATION_DATABASE_URL",
    "maintenance": "FINSET_INTEGRATION_MAINTENANCE_DATABASE_URL",
}
DEDICATED_MARKERS = frozenset({"integration", "finset_integration"})


def synthetic_url(role="runtime", password=None):
    if password is None:
        password = f"synthetic-{role}-password-not-real"
    return (
        f"postgresql+psycopg://finset_integration_{role}_login:{password}"
        "@127.0.0.1:5432/finset_integration"
    )


SYNTHETIC_URL = synthetic_url()
SYNTHETIC_LINES = {
    role: f"{key}={synthetic_url(role)}" for role, key in CREDENTIAL_KEYS.items()
}


@pytest.mark.parametrize("role", CREDENTIAL_KEYS, ids=tuple(CREDENTIAL_KEYS))
def test_target_accepts_dedicated_roles_and_redacts_representations(role):
    target = policy.validate_target(role, synthetic_url(role))
    assert isinstance(target, policy.Target)
    assert target.role == role
    assert target.login == f"finset_integration_{role}_login"
    assert target._password == f"synthetic-{role}-password-not-real"
    assert repr(target) == f"<FinSetTarget role={role}>"
    assert str(target) == repr(target)
    assert "synthetic-" not in repr({role: target})
    assert "postgresql" not in repr({role: target})


def test_target_decodes_password_without_exposing_it_in_repr():
    target = policy.validate_target(
        "runtime", synthetic_url(password="synthetic-%40%3A%23%2F%25-not-real")
    )
    assert target._password == "synthetic-@:#/%-not-real"
    assert repr(target) == "<FinSetTarget role=runtime>"


@pytest.mark.parametrize("value", [
    pytest.param(None, id="missing-value"),
    pytest.param(123, id="non-string-value"),
    pytest.param("", id="empty-value"),
    pytest.param("synthetic-not-a-url", id="malformed-value"),
    pytest.param("service=synthetic_service", id="service-dsn"),
    pytest.param(SYNTHETIC_URL.replace("postgresql+psycopg", "postgresql"), id="wrong-driver"),
    pytest.param(SYNTHETIC_URL.removesuffix("finset_integration") + "finset_test", id="legacy-database"),
    pytest.param(SYNTHETIC_URL.removesuffix("finset_integration") + "finset_dev", id="development-database"),
    pytest.param(SYNTHETIC_URL.removesuffix("finset_integration") + "postgres", id="administrative-database"),
    pytest.param(SYNTHETIC_URL.removesuffix("/finset_integration"), id="missing-database"),
    pytest.param(SYNTHETIC_URL + "/", id="extra-path-segment"),
    pytest.param(SYNTHETIC_URL.removesuffix("finset_integration") + "%66inset_integration", id="encoded-database"),
    pytest.param(SYNTHETIC_URL.replace("127.0.0.1", "localhost"), id="hostname-alias"),
    pytest.param(SYNTHETIC_URL.replace("127.0.0.1", "192.0.2.42"), id="non-loopback-host"),
    pytest.param(SYNTHETIC_URL.replace("127.0.0.1", "synthetic.example.invalid"), id="remote-host"),
    pytest.param(SYNTHETIC_URL.replace("127.0.0.1", "[::1]"), id="different-loopback-host"),
    pytest.param(SYNTHETIC_URL.replace("127.0.0.1", ""), id="missing-host"),
    pytest.param(SYNTHETIC_URL.replace(":5432/", "/"), id="missing-port"),
    pytest.param(SYNTHETIC_URL.replace(":5432/", ":5433/"), id="different-port"),
    pytest.param(SYNTHETIC_URL.replace(":5432/", ":0/"), id="zero-port"),
    pytest.param(SYNTHETIC_URL.replace(":5432/", ":65536/"), id="out-of-range-port"),
    pytest.param(SYNTHETIC_URL.replace(":5432/", ":synthetic-port/"), id="malformed-port"),
    pytest.param(SYNTHETIC_URL.replace("runtime_login", "maintenance_login"), id="wrong-role-login"),
    pytest.param(SYNTHETIC_URL.replace("finset_integration_runtime_login", "synthetic_other_login"), id="other-login"),
    pytest.param(SYNTHETIC_URL.replace("finset_integration_runtime_login", ""), id="missing-login"),
    pytest.param(SYNTHETIC_URL.replace(":synthetic-runtime-password-not-real", ""), id="missing-password"),
    pytest.param(synthetic_url(password=""), id="empty-password"),
    pytest.param(SYNTHETIC_URL.replace("127.0.0.1", "127.0.0.1,192.0.2.42"), id="multiple-hosts"),
    pytest.param(SYNTHETIC_URL.replace(":5432/", ":5432,192.0.2.42:5432/"), id="multiple-host-port-pairs"),
    pytest.param(" " + SYNTHETIC_URL, id="leading-whitespace"),
    pytest.param(SYNTHETIC_URL + "\n", id="trailing-newline"),
    pytest.param(synthetic_url(password="synthetic-raw\npassword-not-real"), id="embedded-newline"),
    pytest.param(synthetic_url(password="synthetic-raw\rpassword-not-real"), id="embedded-carriage-return"),
    pytest.param(synthetic_url(password="synthetic-raw\tpassword-not-real"), id="embedded-tab"),
    pytest.param(SYNTHETIC_URL.replace("127.0.0.1", "127.\n0.0.1"), id="newline-in-host"),
    pytest.param(synthetic_url(password="synthetic-%00-not-real"), id="encoded-nul"),
    pytest.param(synthetic_url(password="synthetic-%09-not-real"), id="encoded-tab"),
    pytest.param(synthetic_url(password="synthetic-%0A-not-real"), id="encoded-newline"),
    pytest.param(synthetic_url(password="synthetic-%0D-not-real"), id="encoded-carriage-return"),
    pytest.param(synthetic_url(password="synthetic-%7F-not-real"), id="encoded-delete-control"),
    pytest.param(synthetic_url(password="synthetic-%GG-not-real"), id="invalid-percent-escape"),
    pytest.param(synthetic_url(password="synthetic-%FF-not-real"), id="invalid-utf8-escape"),
])
def test_target_rejects_unsafe_values_without_echoing_them(value):
    with pytest.raises(policy.SafetyError) as error:
        policy.validate_target("runtime", value)
    assert str(error.value) in {
        "Invalid dedicated connection configuration.",
        "Dedicated connection target, identity, or credential is not permitted.",
    }
    assert "synthetic-" not in repr(error.value)
    assert "postgresql" not in repr(error.value)


@pytest.mark.parametrize("suffix", [
    pytest.param("?dbname=synthetic_other_database", id="dbname-override"),
    pytest.param("?database=synthetic_other_database", id="database-override"),
    pytest.param("?host=synthetic.example.invalid", id="host-override"),
    pytest.param("?hostaddr=192.0.2.42", id="host-address-override"),
    pytest.param("?host=127.0.0.1&host=192.0.2.42", id="repeated-host-override"),
    pytest.param("?port=5433", id="port-override"),
    pytest.param("?user=synthetic_other_login", id="login-override"),
    pytest.param("?password=synthetic-query-password-not-real", id="credential-override"),
    pytest.param("?service=synthetic_service", id="service-override"),
    pytest.param("?servicefile=synthetic-service.conf", id="service-file-override"),
    pytest.param("?options=-csearch_path=synthetic_schema", id="session-options-override"),
    pytest.param("?sslmode=disable", id="transport-override"),
    pytest.param("?connect_timeout=1", id="even-benign-query-disallowed"),
    pytest.param("?", id="empty-query-delimiter"),
    pytest.param("#synthetic-fragment", id="fragment"),
    pytest.param("#", id="empty-fragment-delimiter"),
])
def test_target_rejects_all_query_and_fragment_overrides(suffix):
    with pytest.raises(policy.SafetyError) as error:
        policy.validate_target("runtime", SYNTHETIC_URL + suffix)
    assert str(error.value) == "Dedicated connection target, identity, or credential is not permitted."


@pytest.mark.parametrize("role", [
    pytest.param("owner", id="owner-is-not-a-dedicated-login-role"),
    pytest.param("synthetic_unknown_role", id="unknown-role"),
    pytest.param(SYNTHETIC_URL, id="untrusted-role-is-not-echoed"),
])
def test_target_rejects_unknown_roles_without_echoing_them(role):
    with pytest.raises(policy.SafetyError) as error:
        policy.validate_target(role, SYNTHETIC_URL)
    assert str(error.value) == "Invalid dedicated connection configuration."


def test_credentials_use_three_literal_settings_not_ambient_values(monkeypatch):
    for role, key in CREDENTIAL_KEYS.items():
        monkeypatch.setenv(key, synthetic_url(role, password="synthetic-ambient-password-not-real"))
    targets = policy.parse_credentials("\n".join(SYNTHETIC_LINES.values()))
    assert set(targets) == set(CREDENTIAL_KEYS)
    for role, target in targets.items():
        assert target.role == role
        assert target.login == f"finset_integration_{role}_login"
        assert target._password == f"synthetic-{role}-password-not-real"
    assert "synthetic-" not in repr(targets)
    assert "postgresql" not in repr(targets)


@pytest.mark.parametrize("missing_role", [
    pytest.param("runtime", id="missing-runtime-key"),
    pytest.param("migrator", id="missing-migration-key"),
    pytest.param("maintenance", id="missing-maintenance-key"),
    pytest.param(None, id="empty-text"),
])
def test_credentials_never_fill_missing_settings_from_environment(monkeypatch, missing_role):
    for role, key in CREDENTIAL_KEYS.items():
        monkeypatch.setenv(key, synthetic_url(role))
    for key in ("DATABASE_URL", "TEST_DATABASE_URL", "DEV_DATABASE_URL"):
        monkeypatch.setenv(key, SYNTHETIC_URL)
    text = "\n".join(
        line for role, line in SYNTHETIC_LINES.items()
        if missing_role is not None and role != missing_role
    )
    with pytest.raises(policy.SafetyError, match="All three dedicated integration credentials are required"):
        policy.parse_credentials(text)


@pytest.mark.parametrize("role", CREDENTIAL_KEYS, ids=tuple(CREDENTIAL_KEYS))
def test_credentials_reject_duplicate_keys_even_with_identical_values(role):
    text = "\n".join([*SYNTHETIC_LINES.values(), SYNTHETIC_LINES[role]])
    with pytest.raises(policy.SafetyError, match="Unexpected or duplicate integration credential setting"):
        policy.parse_credentials(text)


@pytest.mark.parametrize("setting", [
    pytest.param(f"SYNTHETIC_UNKNOWN_KEY={SYNTHETIC_URL}", id="unknown-key"),
    pytest.param(f"export {SYNTHETIC_LINES['runtime']}", id="shell-export"),
    pytest.param(f" {SYNTHETIC_LINES['runtime']}", id="leading-key-whitespace"),
    pytest.param(f"{CREDENTIAL_KEYS['runtime']} ={SYNTHETIC_URL}", id="trailing-key-whitespace"),
    pytest.param(f"{CREDENTIAL_KEYS['runtime']}= {SYNTHETIC_URL}", id="value-whitespace"),
    pytest.param(f"{CREDENTIAL_KEYS['runtime']}:{SYNTHETIC_URL}", id="missing-equals"),
    pytest.param(f"{CREDENTIAL_KEYS['runtime']}='{SYNTHETIC_URL}'", id="single-quoted-value"),
    pytest.param(f'{CREDENTIAL_KEYS["runtime"]}="{SYNTHETIC_URL}"', id="double-quoted-value"),
    pytest.param(f"{CREDENTIAL_KEYS['runtime']}=$SYNTHETIC_RUNTIME_URL", id="shell-interpolation"),
    pytest.param(f"{CREDENTIAL_KEYS['runtime']}=${{SYNTHETIC_RUNTIME_URL}}", id="dotenv-interpolation"),
    pytest.param(f"{SYNTHETIC_LINES['runtime']} # synthetic comment", id="inline-comment"),
])
def test_credentials_reject_nonliteral_settings_without_echoing_them(monkeypatch, setting):
    monkeypatch.setenv("SYNTHETIC_RUNTIME_URL", SYNTHETIC_URL)
    text = "\n".join([setting, SYNTHETIC_LINES["migrator"], SYNTHETIC_LINES["maintenance"]])
    with pytest.raises(policy.SafetyError) as error:
        policy.parse_credentials(text)
    assert "synthetic-" not in str(error.value)
    assert "postgresql" not in repr(error.value)
    assert setting not in str(error.value)


def test_credentials_reject_an_extra_fallback_key():
    text = "\n".join([*SYNTHETIC_LINES.values(), f"DATABASE_URL={SYNTHETIC_URL}"])
    with pytest.raises(policy.SafetyError, match="Unexpected or duplicate integration credential setting"):
        policy.parse_credentials(text)


@pytest.mark.parametrize("password", [
    pytest.param("synthetic-runtime-password-not-real", id="duplicate-literal-credential"),
    pytest.param("synthetic-%72untime-password-not-real", id="duplicate-decoded-credential"),
])
def test_credentials_require_distinct_decoded_passwords(password):
    lines = dict(SYNTHETIC_LINES)
    lines["migrator"] = f"{CREDENTIAL_KEYS['migrator']}={synthetic_url('migrator', password)}"
    with pytest.raises(policy.SafetyError) as error:
        policy.parse_credentials("\n".join(lines.values()))
    assert str(error.value) == "Dedicated role credentials must be distinct."


@pytest.fixture
def runtime_identity():
    return {
        "database": "finset_integration",
        "session_user": "finset_integration_runtime_login",
        "current_user": "finset_integration_runtime_login",
        "address": "127.0.0.1",
        "port": 5432,
    }


@pytest.mark.parametrize("role,effective", [
    pytest.param("runtime", None, id="runtime-login"),
    pytest.param("migrator", None, id="migrator-login"),
    pytest.param("maintenance", None, id="maintenance-login"),
    pytest.param("migrator", "finset_owner", id="explicit-owner-effective-role"),
])
def test_identity_accepts_exact_endpoint_and_authenticated_role(runtime_identity, role, effective):
    login = f"finset_integration_{role}_login"
    row = dict(runtime_identity, session_user=login, current_user=effective or login)
    assert policy.validate_identity(row, role, True, effective=effective) is None


@pytest.mark.parametrize("field,value", [
    pytest.param("database", "finset_test", id="legacy-database"),
    pytest.param("database", "synthetic-private-database", id="untrusted-database"),
    pytest.param("session_user", "finset_integration_maintenance_login", id="other-session-login"),
    pytest.param("current_user", "finset_owner", id="unrequested-effective-role"),
    pytest.param("current_user", "synthetic-private-identity", id="untrusted-current-identity"),
    pytest.param("address", "192.0.2.42", id="other-server-address"),
    pytest.param("address", "localhost", id="server-hostname-not-address"),
    pytest.param("port", 5433, id="other-server-port"),
    pytest.param("port", "5432", id="port-must-be-integer"),
])
def test_identity_rejects_mismatches_without_echoing_row_values(runtime_identity, field, value):
    runtime_identity[field] = value
    with pytest.raises(policy.SafetyError) as error:
        policy.validate_identity(runtime_identity, "runtime", True)
    assert str(error.value) == "Connected database, identity, endpoint, or SCRAM authentication is unexpected."


@pytest.mark.parametrize("field", [
    "database", "session_user", "current_user", "address", "port",
], ids=["missing-database", "missing-session-user", "missing-current-user", "missing-address", "missing-port"])
def test_identity_requires_every_reported_field(runtime_identity, field):
    del runtime_identity[field]
    with pytest.raises(policy.SafetyError):
        policy.validate_identity(runtime_identity, "runtime", True)


def test_identity_requires_password_authentication(runtime_identity):
    with pytest.raises(policy.SafetyError, match="SCRAM authentication is unexpected"):
        policy.validate_identity(runtime_identity, "runtime", False)


def test_identity_requires_the_requested_effective_role(runtime_identity):
    with pytest.raises(policy.SafetyError):
        policy.validate_identity(runtime_identity, "runtime", True, effective="finset_owner")


@pytest.mark.parametrize("role", ["runtime", "maintenance"])
def test_identity_never_authorizes_owner_assumption_for_application_roles(runtime_identity, role):
    row = dict(runtime_identity, session_user=policy.ROLES[role][1], current_user="finset_owner")
    with pytest.raises(policy.SafetyError):
        policy.validate_identity(row, role, True, effective="finset_owner")


def test_identity_rejects_unknown_roles_without_exposing_input(runtime_identity):
    with pytest.raises(policy.SafetyError) as error:
        policy.validate_identity(runtime_identity, "synthetic-untrusted-role", True)
    assert "synthetic-untrusted-role" not in str(error.value)


@pytest.mark.parametrize("args", [
    pytest.param(["--showlocals"], id="show-locals"),
    pytest.param(["--showlocals=true"], id="show-locals-equals"),
    pytest.param(["-l"], id="short-show-locals"),
    pytest.param(["-vl"], id="combined-short-show-locals"),
    pytest.param(["-s"], id="disable-capture"),
    pytest.param(["--capture=no"], id="capture-override"),
    pytest.param(["--show-capture=all"], id="capture-reporting"),
    pytest.param(["--junitxml=synthetic-report.xml"], id="junit-report"),
    pytest.param(["--junit-xml", "synthetic-report.xml"], id="junit-report-alias"),
    pytest.param(["--html=synthetic-report.html"], id="html-report"),
    pytest.param(["--json-report"], id="json-report"),
    pytest.param(["--log-file=synthetic-report.log"], id="log-file"),
    pytest.param(["--log-cli-level=DEBUG"], id="live-logging"),
    pytest.param(["--log-level=DEBUG"], id="log-level"),
    pytest.param(["-c", "synthetic-pytest.ini"], id="config-file"),
    pytest.param(["-csynthetic-pytest.ini"], id="attached-config-file"),
    pytest.param(["-o", "addopts=-l"], id="ini-override"),
    pytest.param(["-oaddopts=-l"], id="attached-ini-override"),
    pytest.param(["--override-ini=addopts=-l"], id="long-ini-override"),
    pytest.param(["--addopts=-l"], id="addopts-override"),
    pytest.param(["--confcutdir=synthetic-tests"], id="conftest-boundary-override"),
    pytest.param(["--rootdir=synthetic-root"], id="root-directory-override"),
    pytest.param(["--pyargs", "synthetic_package"], id="package-path-override"),
    pytest.param(["-p", "synthetic_plugin"], id="plugin-injection"),
    pytest.param(["-psynthetic_plugin"], id="attached-plugin-injection"),
    pytest.param(["-p", "no:tests.integration_finset.safety"], id="disable-safety-plugin"),
    pytest.param(["-n", "2"], id="workers"),
    pytest.param(["-n2"], id="attached-workers"),
    pytest.param(["--numprocesses=2"], id="long-workers"),
    pytest.param(["--continue-on-collection-errors"], id="ignore-collection-failures"),
    pytest.param(["--cache-clear"], id="cache-mutation"),
])
def test_invocation_rejects_unsafe_overrides(args):
    with pytest.raises(policy.SafetyError) as error:
        policy.validate_invocation(["--run-finset-integration", *args])
    assert str(error.value) == "Unsafe reporting, plugin, configuration, path, or worker option."


@pytest.mark.parametrize("args", [
    pytest.param(["--run-finset-integration"], id="explicit-opt-in"),
    pytest.param(["--run-finset-integration", "--collect-only", "-q"], id="collection-review"),
    pytest.param(
        ["--run-finset-integration", "-vv", "-k", "synthetic_case", "-m",
         "integration and finset_integration and not finset_committed"],
        id="restricted-selection-and-verbosity",
    ),
])
def test_invocation_permits_controlled_launcher_options(args):
    assert policy.validate_invocation(args) is None


@pytest.mark.parametrize("keyword,marker", [
    ("", "integration and finset_integration and not finset_committed"),
    ("not hash", "integration"),
])
def test_selectors_accept_valid_expressions(keyword, marker):
    assert policy.validate_selectors(keyword, marker) is None


@pytest.mark.parametrize("keyword,marker", [
    pytest.param(SYNTHETIC_URL, "integration", id="credential-url-in-keyword"),
    pytest.param("", SYNTHETIC_URL, id="credential-url-in-marker"),
    pytest.param("(", "integration", id="unclosed-keyword"),
    pytest.param("", "integration and", id="incomplete-marker"),
    pytest.param("", "synthetic_unknown_marker", id="unregistered-marker-name"),
])
def test_selector_errors_do_not_echo_input(keyword, marker):
    with pytest.raises(policy.SafetyError) as error:
        policy.validate_selectors(keyword, marker)
    assert str(error.value) == "Invalid test selector; supplied values are withheld."


def test_unexpected_parser_exceptions_are_sanitized(monkeypatch):
    from _pytest.mark.expression import Expression

    def parser_failure(cls, value):
        raise RuntimeError("synthetic parser failure: " + SYNTHETIC_URL)

    monkeypatch.setattr(Expression, "compile", classmethod(parser_failure))
    with pytest.raises(policy.SafetyError) as error:
        policy.validate_selectors("", "integration")
    assert str(error.value) == "Invalid test selector; supplied values are withheld."


def test_report_redaction_preserves_skip_tuple_and_sanitizes_xfail():
    report = SimpleNamespace(
        longrepr=("synthetic_test.py", 7, SYNTHETIC_URL),
        sections=[("Captured stdout", "synthetic-private-value")],
        wasxfail="synthetic-private-value",
    )
    policy.redact_report(report, ["synthetic-private-value"])
    assert report.longrepr == ("synthetic_test.py", 7, "[REDACTED_CONNECTION_URL]")
    assert report.sections == [("Captured stdout", "[REDACTED]")]
    assert report.wasxfail == "[REDACTED]"


def test_report_redaction_sanitizes_collection_and_failure_text():
    report = SimpleNamespace(longrepr="Invalid value: " + SYNTHETIC_URL, sections=[])
    policy.redact_report(report)
    assert report.longrepr == "Invalid value: [REDACTED_CONNECTION_URL]"


def test_selection_accepts_only_dedicated_rollback_items():
    items = [
        (policy.SUITE / "test_synthetic.py", DEDICATED_MARKERS),
        (policy.SUITE / "nested" / "test_synthetic.py", DEDICATED_MARKERS | {"synthetic_extra"}),
    ]
    assert policy.validate_selection(items, opted_in=True) is None


def test_selection_requires_opt_in_even_for_dedicated_items():
    items = [(policy.SUITE / "test_synthetic.py", DEDICATED_MARKERS)]
    with pytest.raises(policy.SafetyError, match="Explicit --run-finset-integration is required"):
        policy.validate_selection(items, opted_in=False)


def test_selection_rejects_zero_items():
    with pytest.raises(policy.SafetyError, match="No dedicated FinSet tests were selected"):
        policy.validate_selection([], opted_in=True)


@pytest.mark.parametrize("name", ["factory", "case", "runtime", "maintenance", "migrator", "data", "maintenance_data"])
def test_selection_rejects_parameters_that_shadow_live_fixtures(name):
    items = [(policy.SUITE / "test_synthetic.py", DEDICATED_MARKERS)]
    with pytest.raises(policy.SafetyError, match="fixture names may not be shadowed"):
        policy.validate_selection(items, opted_in=True, parameter_names=[name])


def test_selection_accepts_domain_parameter_names():
    items = [(policy.SUITE / "test_synthetic.py", DEDICATED_MARKERS)]
    assert policy.validate_selection(items, opted_in=True, parameter_names=["builder", "column", "value"]) is None


@pytest.mark.parametrize("path", [
    pytest.param(policy.SUITE.parent / "test_config.py", id="legacy-path-with-forged-markers"),
    pytest.param(policy.SUITE.parent / "test_integration_safety.py", id="unit-test-path"),
    pytest.param(policy.BACKEND / "app" / "synthetic.py", id="outside-tests-directory"),
    pytest.param(policy.SUITE.parent / "integration_finset_extra" / "test_synthetic.py", id="sibling-prefix"),
    pytest.param(policy.SUITE / ".." / "test_config.py", id="parent-traversal"),
])
def test_selection_rejects_paths_outside_the_suite(path):
    with pytest.raises(policy.SafetyError, match="Legacy, mixed, or unintended test selection"):
        policy.validate_selection([(path, DEDICATED_MARKERS)], opted_in=True)


@pytest.mark.parametrize("markers", [
    pytest.param(set(), id="unmarked"),
    pytest.param({"integration"}, id="missing-dedicated-marker"),
    pytest.param({"finset_integration"}, id="missing-integration-marker"),
])
def test_selection_requires_both_markers(markers):
    with pytest.raises(policy.SafetyError, match="Legacy, mixed, or unintended test selection"):
        policy.validate_selection([(policy.SUITE / "test_synthetic.py", markers)], opted_in=True)


def test_selection_rejects_mixed_legacy_and_dedicated_items():
    items = [
        (policy.SUITE / "test_synthetic.py", DEDICATED_MARKERS),
        (policy.SUITE.parent / "test_config.py", {"integration"}),
    ]
    with pytest.raises(policy.SafetyError, match="Legacy, mixed, or unintended test selection"):
        policy.validate_selection(items, opted_in=True)


@pytest.mark.parametrize("committed_marker,allow_commits", [
    pytest.param(True, False, id="committed-marker-without-flag"),
    pytest.param(True, True, id="committed-marker-with-flag"),
    pytest.param(False, True, id="allow-flag-on-rollback-selection"),
])
def test_selection_never_allows_commits_in_stage_a(committed_marker, allow_commits):
    markers = DEDICATED_MARKERS | ({"finset_committed"} if committed_marker else set())
    with pytest.raises(policy.SafetyError, match="Stage A"):
        policy.validate_selection(
            [(policy.SUITE / "test_synthetic.py", markers)],
            opted_in=True, allow_commits=allow_commits,
        )


@pytest.fixture
def owned_scope():
    registry = scope.Scope()
    registry.register("users", {"id": UUID(int=1), "email": registry.email()}, "runtime")
    registry.register(
        "categories",
        {"id": UUID(int=2), "owner_user_id": UUID(int=1), "name": registry.label()},
        "runtime",
    )
    return registry


def test_scope_tokens_labels_and_emails_are_synthetic_and_distinct():
    first, second = scope.Scope(), scope.Scope()
    assert UUID(hex=first.token).hex == first.token
    assert UUID(hex=second.token).hex == second.token
    assert first.token != second.token
    first_label, second_label = first.label("row_1"), first.label("row_1")
    assert first_label != second_label
    assert first_label.startswith(f"fsit_{first.token}_")
    assert first_label.endswith("_row_1")
    email = first.email("USER")
    assert email == email.lower()
    assert email.startswith(f"fsit_{first.token}_")
    assert email.endswith("_user@example.invalid")


@pytest.mark.parametrize("label", [
    pytest.param("", id="empty-label"),
    pytest.param("../row", id="path-label"),
    pytest.param("two words", id="whitespace-label"),
    pytest.param("row\nname", id="newline-label"),
    pytest.param("*", id="wildcard-label"),
    pytest.param("%all", id="prefix-selector-label"),
    pytest.param("--", id="punctuation-only-label"),
    pytest.param("x" * 17, id="overlong-label"),
])
def test_scope_rejects_unsafe_labels(label):
    with pytest.raises(policy.SafetyError, match="Invalid synthetic fixture label"):
        scope.Scope().label(label)


def test_scope_registers_own_receipts_with_table_owner_and_role(owned_scope):
    user, = owned_scope.records("users")
    category, = owned_scope.records("categories")
    transaction = owned_scope.register(
        "transactions", {"id": UUID(int=3), "user_id": user.id}, "runtime"
    )
    system_category = owned_scope.register(
        policy.VIEW, {"id": UUID(int=4), "owner_user_id": None}, "maintenance"
    )
    assert user.owner_id == user.id
    assert category.owner_id == transaction.owner_id == user.id
    assert system_category.owner_id is None
    assert system_category.role == "maintenance"
    assert owned_scope.records() == (user, category, transaction, system_category)
    assert owned_scope.records("plans") == ()
    for record in owned_scope.records():
        assert isinstance(record, scope.Record)
        assert owned_scope.require(record) is record
        assert record.values["id"] == record.id


def test_scope_copies_receipt_values_instead_of_adopting_the_input_mapping():
    registry = scope.Scope()
    row = {"id": UUID(int=1), "email": "synthetic-original@example.invalid"}
    record = registry.register("users", row, "runtime")
    row["email"] = "synthetic-replacement@example.invalid"
    row["id"] = UUID(int=99)
    assert record.values == {"id": UUID(int=1), "email": "synthetic-original@example.invalid"}
    assert record.values is not row
    assert registry.require(record) is record


@pytest.mark.parametrize("table,row", [
    pytest.param("synthetic_unknown_table", {"id": UUID(int=3)}, id="unknown-table"),
    pytest.param("public.users", {"id": UUID(int=3)}, id="qualified-table"),
    pytest.param("users", {}, id="missing-id"),
    pytest.param("users", {"id": None}, id="null-id"),
    pytest.param("users", {"id": 3}, id="integer-id"),
    pytest.param("users", {"id": str(UUID(int=3))}, id="text-not-uuid"),
])
def test_scope_rejects_invalid_insert_receipts_without_mutation(owned_scope, table, row):
    before = owned_scope.records()
    with pytest.raises(policy.SafetyError, match="Unexpected synthetic insert receipt"):
        owned_scope.register(table, row, "runtime")
    assert owned_scope.records() == before


@pytest.mark.parametrize("table,owner_field", [
    pytest.param("categories", "owner_user_id", id="category-owner"),
    pytest.param("transactions", "user_id", id="transaction-owner"),
])
def test_scope_requires_a_registered_parent(owned_scope, table, owner_field):
    with pytest.raises(policy.SafetyError, match="unregistered parent"):
        owned_scope.register(table, {"id": UUID(int=3), owner_field: UUID(int=99)}, "runtime")


def test_scope_rejects_foreign_receipts_parents_and_cleanup_ids(owned_scope):
    foreign = scope.Scope()
    foreign_user = foreign.register("users", {"id": UUID(int=99)}, "runtime")
    with pytest.raises(policy.SafetyError, match="Unknown, cross-scope, or rebound"):
        owned_scope.require(foreign_user)
    with pytest.raises(policy.SafetyError, match="unregistered parent"):
        owned_scope.register(
            "categories", {"id": UUID(int=3), "owner_user_id": foreign_user.id}, "runtime"
        )
    with pytest.raises(policy.SafetyError, match="unknown records or use broad selectors"):
        scope.validate_cleanup_scope(owned_scope, "users", [foreign_user.id])
    assert foreign.require(foreign_user) is foreign_user


@pytest.mark.parametrize("changes", [
    pytest.param({"id": UUID(int=99)}, id="unknown-id"),
    pytest.param({"table": "transactions"}, id="rebound-table"),
    pytest.param({"owner_id": UUID(int=99)}, id="rebound-owner"),
    pytest.param({"role": "maintenance"}, id="rebound-role"),
])
def test_scope_rejects_unknown_or_rebound_records(owned_scope, changes):
    record, = owned_scope.records("categories")
    with pytest.raises(policy.SafetyError, match="Unknown, cross-scope, or rebound"):
        owned_scope.require(replace(record, **changes))
    assert owned_scope.require(record) is record


@pytest.mark.parametrize("value", [
    pytest.param(None, id="null-record"),
    pytest.param(UUID(int=2), id="bare-id"),
    pytest.param({"table": "categories", "id": UUID(int=2)}, id="mapping-not-receipt"),
    pytest.param("fsit_%", id="prefix-not-receipt"),
])
def test_scope_requires_a_record_not_a_selector(owned_scope, value):
    with pytest.raises(policy.SafetyError, match="An exact registered record is required"):
        owned_scope.require(value)


@pytest.mark.parametrize("changes,role", [
    pytest.param({}, "runtime", id="identical-duplicate"),
    pytest.param({"name": "synthetic-replacement"}, "runtime", id="changed-values"),
    pytest.param({"owner_user_id": UUID(int=3)}, "runtime", id="changed-owner"),
    pytest.param({}, "maintenance", id="changed-role"),
])
def test_scope_never_registers_an_existing_receipt_again(owned_scope, changes, role):
    original, = owned_scope.records("categories")
    owned_scope.register("users", {"id": UUID(int=3)}, "runtime")
    with pytest.raises(policy.SafetyError, match="adopt an existing receipt"):
        owned_scope.register("categories", dict(original.values, **changes), role)
    assert owned_scope.records("categories") == (original,)
    assert owned_scope.require(original) is original


def test_cleanup_validation_returns_only_requested_receipts_without_mutation(owned_scope):
    first, = owned_scope.records("categories")
    second = owned_scope.register(
        "categories", {"id": UUID(int=3), "owner_user_id": first.owner_id}, "runtime"
    )
    before = tuple((record, dict(record.values)) for record in owned_scope.records())
    selected = scope.validate_cleanup_scope(owned_scope, "categories", [second.id, first.id])
    assert len(selected) == 2
    assert selected[0] is second
    assert selected[1] is first
    assert scope.validate_cleanup_scope(owned_scope, "categories", [first.id]) == (first,)
    assert tuple((record, dict(record.values)) for record in owned_scope.records()) == before


@pytest.mark.parametrize("ids", [
    pytest.param([], id="empty-allowlist"),
    pytest.param([UUID(int=99)], id="unknown-id"),
    pytest.param([UUID(int=2), UUID(int=99)], id="mixed-known-and-unknown-ids"),
    pytest.param([UUID(int=1)], id="parent-id-is-not-a-child-selector"),
    pytest.param([UUID(int=2), UUID(int=2)], id="duplicate-known-id"),
    pytest.param([str(UUID(int=2))], id="text-not-uuid"),
    pytest.param([2], id="integer-not-uuid"),
    pytest.param([None], id="null-not-uuid"),
    pytest.param(["*"], id="wildcard-selector"),
    pytest.param("fsit_%", id="prefix-selector"),
    pytest.param(["email LIKE '%@example.invalid'"], id="email-selector"),
    pytest.param({"owner_user_id": UUID(int=1)}, id="owner-mapping-selector"),
    pytest.param([{"owner_user_id": UUID(int=1)}], id="unhashable-selector"),
])
def test_cleanup_validation_rejects_nonexact_allowlists_without_mutation(owned_scope, ids):
    before = owned_scope.records()
    with pytest.raises(policy.SafetyError):
        scope.validate_cleanup_scope(owned_scope, "categories", ids)
    assert owned_scope.records() == before


@pytest.mark.parametrize("table", [
    pytest.param("synthetic_unknown_table", id="unknown-table"),
    pytest.param("public.categories", id="qualified-table"),
    pytest.param("categories*", id="table-prefix"),
    pytest.param("categories WHERE TRUE", id="broad-predicate"),
    pytest.param("categories; DELETE FROM users", id="statement-injection"),
    pytest.param("*", id="all-tables"),
])
def test_cleanup_validation_rejects_unapproved_tables(owned_scope, table):
    with pytest.raises(policy.SafetyError, match="Unapproved cleanup table"):
        scope.validate_cleanup_scope(owned_scope, table, [UUID(int=2)])
