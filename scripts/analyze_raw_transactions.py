#!/usr/bin/env python3
"""Run the baseline analyzer from a source checkout without installation."""

from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from witness_resource_accounting.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
