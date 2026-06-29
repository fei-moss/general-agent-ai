"""Idempotency helpers for chat acceptance."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def chat_request_hash(
    *,
    message: str,
    conversation_id: str | None,
    metadata: dict[str, Any] | None,
) -> str:
    """Return a stable hash for idempotency replay comparison."""
    payload = {
        "conversation_id": conversation_id,
        "message": message,
        "metadata": metadata or {},
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
