#!/usr/bin/env python3
"""Stable DockerHost release entrypoint.

Actions: deploy, redeploy, rollback, smoke, destroy. Mutations require
--execute and may write --audit-json. The implementation preserves the
"stream=false 422 smoke", "rollback previous SHA", and
"destroy disposable environment" release gates.
Chat smoke uses X-Marketplace-User-ID, X-Marketplace-Wallet, and the matching
marketplace_identity payload contract.
"""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dockerhost.release_cli import (  # noqa: E402
    Runner,
    Step,
    _validate_completed_step,
    main,
)

__all__ = ["Runner", "Step", "_validate_completed_step", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
