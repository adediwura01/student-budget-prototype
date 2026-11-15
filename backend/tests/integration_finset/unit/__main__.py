"""Fixed Stage B test selection, with its canary active before pytest imports tests."""

import os
from pathlib import Path
import sys


def main():
    if any(value in sys.argv[1:] for value in ("-l", "--showlocals", "-s")):
        raise SystemExit("Unsafe reporting is prohibited in Stage B.")
    if any(value not in ("-q", "-v", "-vv") for value in sys.argv[1:]):
        raise SystemExit("Stage B accepts only verbosity flags; test paths and plugins are fixed.")
    os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    os.environ.pop("PYTEST_ADDOPTS", None)
    os.environ.pop("PYTEST_PLUGINS", None)
    sys.dont_write_bytecode = True
    from . import guard
    import pytest
    root = Path(__file__).resolve().parent
    args = ["-c", str(root / "pytest.ini"),
            "--confcutdir", str(root), str(root), str(guard.LEGACY_SAFETY), "--tb=short",
            "--strict-markers", "--maxfail=1", "-p", "no:cacheprovider", *sys.argv[1:]]
    return pytest.main(args, plugins=[guard])


if __name__ == "__main__":
    raise SystemExit(main())
