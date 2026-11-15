"""One owned child. Secret registration uses a private pipe, never public output."""

import os
import sys

from .policy import BACKEND, PLUGIN, SUITE, SafetyError, validate_selectors


def run_spec(spec, control):
    mode = spec.get("mode")
    if mode == "probe":
        from .unit import guard
        guard.install()
        from .probes import run
        return run(spec.get("probe"), control)
    allowed = {"mode", "opted_in", "k", "m", "q", "v"}
    if (mode not in ("live", "collect") or set(spec) != allowed or spec["opted_in"] is not True
            or not isinstance(spec["k"], str) or not isinstance(spec["m"], str)
            or not isinstance(spec["q"], bool) or type(spec["v"]) is not int
            or not 0 <= spec["v"] <= 3):
        raise SafetyError("The supervised test specification is invalid.")
    if os.environ.get("PYTEST_ADDOPTS") or os.environ.get("PYTEST_PLUGINS"):
        raise SafetyError("Ambient pytest overrides are prohibited in the child.")
    os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    sys.dont_write_bytecode = True
    validate_selectors(spec["k"], spec["m"])
    from . import safety
    safety.attach_supervisor(control)
    if mode == "collect":
        control.secret_registration([])
    import pytest
    args = ["-p", PLUGIN, "-c", str(BACKEND / "pytest.ini"), "--confcutdir", str(BACKEND / "tests"),
            str(SUITE), "--run-finset-integration", "--strict-markers", "--maxfail=1", "--color=no",
            "-p", "no:cacheprovider", "-m", spec["m"]]
    if spec["k"]:
        args.extend(["-k", spec["k"]])
    if mode == "collect":
        args.append("--collect-only")
    if spec["q"]:
        args.append("-q")
    args.extend(["-v"] * spec["v"])
    safety.authorize_launcher(args)
    try:
        return pytest.main(args)
    finally:
        # Parent retains its filter until every captured descriptor has drained.
        safety.release_secrets()


def main():
    if len(sys.argv) != 3 or sys.argv[1] != "--control" or not sys.argv[2].isdigit():
        return 4
    from .supervisor import ControlError, open_control
    control = open_control(int(sys.argv[2]))
    try:
        return run_spec(control.receive_spec(), control) or 0
    except (SafetyError, ControlError):
        print("Supervised child rejected configuration or encountered an unsafe condition.", file=sys.stderr)
        return 4
    finally:
        control.close()


if __name__ == "__main__":
    raise SystemExit(main())
