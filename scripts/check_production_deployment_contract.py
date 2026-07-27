#!/usr/bin/env python3
"""Run the production deployment contract validator."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.production_deployment_validator import main


if __name__ == "__main__":
    raise SystemExit(main())
