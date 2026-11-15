"""Controlled launcher. Importing this module does not start pytest."""

import argparse
import os
import sys

from .policy import SafetyError, validate_invocation, validate_selectors


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise SafetyError("Unsupported or invalid FinSet test option; supplied values are withheld.")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        validate_invocation(argv)
        parser = Parser(description="Explicit, rollback-only FinSet integration profile.", allow_abbrev=False)
        parser.add_argument("--run-finset-integration", action="store_true")
        parser.add_argument("--allow-finset-commits", action="store_true")
        parser.add_argument("--collect-only", action="store_true")
        parser.add_argument("-k", default="")
        parser.add_argument("-m", default="integration and finset_integration and not finset_committed")
        parser.add_argument("-q", action="store_true")
        parser.add_argument("-v", action="count", default=0)
        options = parser.parse_args(argv)
        if not options.run_finset_integration:
            raise SafetyError("Explicit --run-finset-integration is required, including collection review.")
        if options.allow_finset_commits:
            raise SafetyError("Committed execution is not implemented or authorized by Stage A.")
        if options.v > 3:
            raise SafetyError("The controlled launcher accepts at most three verbosity flags.")
        if os.environ.get("PYTEST_ADDOPTS") or os.environ.get("PYTEST_PLUGINS"):
            raise SafetyError("Ambient pytest options/plugins must be removed before this controlled run.")
        os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
        os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
        sys.dont_write_bytecode = True
        validate_selectors(options.k, options.m)
        from .supervisor import supervise
        spec = {"mode": "collect" if options.collect_only else "live",
                "opted_in": True, "k": options.k, "m": options.m,
                "q": options.q, "v": options.v}
        result = supervise(spec)
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        return result.exit_code
    except SafetyError as error:
        print(str(error), file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
