"""DB-free target, invocation, and statement checks. Never echo caller input."""

from dataclasses import dataclass, field
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit


BACKEND = Path(__file__).resolve().parents[2]
SUITE = Path(__file__).resolve().parent
ENV_FILE = BACKEND / ".env.integration"
DATABASE = "finset_integration"
HOST = "127.0.0.1"
PORT = 5432
REVISION = "0001"
PLUGIN = "tests.integration_finset.safety"
ROLES = {
    "runtime": ("FINSET_INTEGRATION_RUNTIME_DATABASE_URL", "finset_integration_runtime_login"),
    "migrator": ("FINSET_INTEGRATION_MIGRATION_DATABASE_URL", "finset_integration_migrator_login"),
    "maintenance": ("FINSET_INTEGRATION_MAINTENANCE_DATABASE_URL", "finset_integration_maintenance_login"),
}
TABLES = (
    "users", "categories", "transactions", "plans", "monthly_budgets",
    "budget_limits", "budget_alerts", "login_sessions", "auth_tokens",
)
VIEW = "finset_system_categories"
GROUPS = ("finset_runtime", "finset_migrator", "finset_owner", "finset_maintenance")


class SafetyError(RuntimeError):
    """A fail-closed test-harness error containing no supplied values."""


@dataclass(frozen=True, repr=False)
class Target:
    role: str
    login: str
    _password: str = field(repr=False)

    def __repr__(self):
        return f"<FinSetTarget role={self.role}>"


def validate_target(role, value):
    __tracebackhide__ = True
    if (not isinstance(role, str) or role not in ROLES
            or not isinstance(value, str) or value != value.strip()
            or any(ord(char) <= 32 or ord(char) == 127 for char in value)
            or re.search(r"%(?![0-9A-Fa-f]{2})", value)):
        raise SafetyError("Invalid dedicated connection configuration.")
    try:
        url = urlsplit(value)
        password = unquote(url.password or "", errors="strict")
        actual = (url.scheme, url.hostname, url.port, url.path, url.username)
    except (ValueError, TypeError, UnicodeError):
        raise SafetyError("Invalid dedicated connection configuration.") from None
    expected = ("postgresql+psycopg", HOST, PORT, "/" + DATABASE, ROLES[role][1])
    if (actual != expected or url.query or url.fragment or "?" in value or "#" in value
            or not password or any(ord(char) < 32 or ord(char) == 127 for char in password)):
        raise SafetyError("Dedicated connection target, identity, or credential is not permitted.")
    return Target(role, ROLES[role][1], password)


def parse_credentials(text):
    """Accept only the provisioning file's literal KEY=URL format, without interpolation."""
    __tracebackhide__ = True
    expected = {value[0]: role for role, value in ROLES.items()}
    values = {}
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator or key not in expected or key in values:
            raise SafetyError("Unexpected or duplicate integration credential setting.")
        values[key] = value
    if set(values) != set(expected):
        raise SafetyError("All three dedicated integration credentials are required.")
    targets = {role: validate_target(role, values[key]) for key, role in expected.items()}
    if len({target._password for target in targets.values()}) != 3:
        raise SafetyError("Dedicated role credentials must be distinct.")
    return targets


def load_credentials():
    __tracebackhide__ = True
    try:
        if ENV_FILE.is_symlink() or not ENV_FILE.is_file():
            raise SafetyError("The dedicated integration credential file is unavailable.")
        text = ENV_FILE.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        raise SafetyError("The dedicated integration credential file is unreadable.") from None
    return parse_credentials(text)


def validate_identity(row, role, password_used, *, effective=None):
    if (not isinstance(role, str) or role not in ROLES or not isinstance(row, dict)
            or effective is not None and (role != "migrator" or effective != "finset_owner")):
        raise SafetyError("Connected database, identity, endpoint, or SCRAM authentication is unexpected.")
    expected = (DATABASE, ROLES[role][1], effective or ROLES[role][1], HOST, PORT)
    actual = tuple(row.get(key) for key in ("database", "session_user", "current_user", "address", "port"))
    if actual != expected or not password_used:
        raise SafetyError("Connected database, identity, endpoint, or SCRAM authentication is unexpected.")


def validate_invocation(args):
    """Only the controlled launcher may supply paths, plugins, config, or reporting."""
    unsafe = {
        "-l", "--showlocals", "-s", "--show-capture", "--capture", "--junitxml", "--junit-xml",
        "--html", "--json-report", "--log-file", "--log-cli-level", "--log-level",
        "--override-ini", "-o", "--addopts", "-p", "-c", "--confcutdir", "--rootdir",
        "--pyargs", "--continue-on-collection-errors", "--cache-clear", "-n", "--numprocesses",
    }
    for argument in args:
        option = argument.split("=", 1)[0]
        if option in unsafe or (argument.startswith("-") and not argument.startswith("--")
                                and any(char in argument[1:] for char in "lspcon")):
            raise SafetyError("Unsafe reporting, plugin, configuration, path, or worker option.")


def validate_selectors(keyword, marker):
    """Pytest otherwise echoes malformed selectors before runtest redaction runs."""
    __tracebackhide__ = True

    def marker_identifiers(expression):
        """Cover every token; evaluation would miss short-circuited marker names."""
        # Only bare marker words, boolean operators, parentheses, and pytest whitespace.
        lexer = re.compile(r"[ \t]+|[()]|[A-Za-z_][A-Za-z0-9_]*")
        identifiers = set()
        position = 0
        while position < len(expression):
            token = lexer.match(expression, position)
            if token is None:
                raise SafetyError("Invalid test selector; supplied values are withheld.")
            value = token.group(0)
            if not value.isspace() and value not in ("and", "or", "not", "(", ")"):
                identifiers.add(value)
            position = token.end()
        return identifiers

    try:
        from _pytest.mark.expression import Expression

        Expression.compile(keyword)
        # The shared parser accepts marker calls, but pytest's -k forbids call kwargs.
        if "=" in keyword:
            raise SafetyError("Invalid test selector; supplied values are withheld.")
        Expression.compile(marker)
        allowed = {"integration", "finset_integration", "finset_committed", "finset_concurrency"}
        if marker_identifiers(marker) - allowed:
            raise SafetyError("Invalid test selector; supplied values are withheld.")
    except (ImportError, AttributeError):
        raise SafetyError("Required pytest selector validation is unavailable; execution is prohibited.") from None
    except Exception:
        # Parser exception classes vary by pytest version and can contain the input.
        raise SafetyError("Invalid test selector; supplied values are withheld.") from None


def validate_selection(items, *, opted_in, allow_commits=False, parameter_names=()):
    """Items are (resolved path, marker-name set); this function never loads credentials."""
    if not opted_in:
        raise SafetyError("Explicit --run-finset-integration is required.")
    if allow_commits:
        raise SafetyError("Stage A has no reviewed committed fixtures or cleanup; commits remain disabled.")
    if not items:
        raise SafetyError("No dedicated FinSet tests were selected.")
    protected = {"factory", "case", "runtime", "maintenance", "migrator", "data", "maintenance_data"}
    if protected.intersection(parameter_names):
        raise SafetyError("Live fixture names may not be shadowed by test parameters.")
    for path, markers in items:
        path = Path(path).resolve()
        if not path.is_relative_to(SUITE) or not {"integration", "finset_integration"} <= set(markers):
            raise SafetyError("Legacy, mixed, or unintended test selection is prohibited.")
        if "finset_committed" in markers:
            raise SafetyError("Committed tests are not executable in Stage A.")


def validate_read_query(statement):
    """Deliberately narrower than SQL: catalog inquiry only, not a general SQL escape hatch."""
    if not isinstance(statement, str) or not re.match(r"^\s*SELECT\b", statement, re.I):
        raise SafetyError("Only read-only catalog inquiries are permitted here.")
    if any(token in statement for token in (";", "--", "/*", "*/")):
        raise SafetyError("Multiple statements and SQL comments are prohibited.")
    forbidden = r"\b(INSERT|UPDATE|DELETE|INTO|CREATE|ALTER|DROP|TRUNCATE|GRANT|REVOKE|COPY|CALL|DO|COMMIT|ROLLBACK|SAVEPOINT|RESET|DISCARD|SET|FOR\s+(?:UPDATE|SHARE)|set_config|nextval|setval|dblink\w*|lo_import|lo_export|pg_read_file|pg_write_file|pg_sleep|pg_terminate_backend|pg_cancel_backend|pg_advisory\w*)\b"
    if re.search(forbidden, statement, re.I):
        raise SafetyError("Side-effecting or transaction-control SQL is prohibited.")
    if re.search(r"\bpublic\s*\.", statement, re.I):
        raise SafetyError("Application reads must use the exact-ID scoped data interface.")


def safe_identifier(value):
    return value if isinstance(value, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,127}", value) else None


def redact(text, secrets=()):
    text = str(text)
    for secret in sorted((item for item in secrets if item), key=len, reverse=True):
        text = text.replace(secret, "[REDACTED]")
    return re.sub(r"(?i)postgres(?:ql)?(?:\+[a-z0-9_]+)?://[^\s]+", "[REDACTED_CONNECTION_URL]", text)


def redact_report(report, secrets=()):
    """Retain pytest's skipped-report tuple while sanitizing displayed fields."""
    __tracebackhide__ = True
    if isinstance(report.longrepr, tuple):
        report.longrepr = tuple(redact(value, secrets) if isinstance(value, str) else value
                                for value in report.longrepr)
    elif report.longrepr:
        report.longrepr = redact(str(report.longrepr), secrets)
    report.sections = [(redact(title, secrets), redact(body, secrets))
                       for title, body in report.sections]
    if hasattr(report, "wasxfail"):
        report.wasxfail = redact(report.wasxfail, secrets)
