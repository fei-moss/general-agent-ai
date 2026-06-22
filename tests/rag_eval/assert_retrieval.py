from __future__ import annotations

import json
from typing import Any


def get_assert(output: str, context: dict[str, Any]) -> dict[str, Any]:
    """Promptfoo Python assertion for retrieval hit quality."""
    vars_ = context.get("vars") or {}
    relevant_doc_ids = set(_as_list(vars_.get("relevant_doc_ids")))
    max_rank = int(vars_.get("max_rank") or vars_.get("top_k") or 3)

    try:
        payload = json.loads(output)
    except json.JSONDecodeError as exc:
        return {"pass": False, "score": 0, "reason": f"invalid json output: {exc}"}

    if payload.get("degraded"):
        return {
            "pass": False,
            "score": 0,
            "reason": f"retrieval degraded: {payload.get('reason')}",
        }

    hits = payload.get("hits") or []
    if not relevant_doc_ids:
        return {"pass": True, "score": 1, "reason": "no relevant_doc_ids configured"}
    if not hits:
        return {"pass": False, "score": 0, "reason": "no retrieval hits returned"}

    for hit in hits:
        rank = int(hit.get("rank") or 0)
        if rank <= max_rank and hit.get("doc_id") in relevant_doc_ids:
            score = max(0.0, (max_rank - rank + 1) / max_rank)
            return {
                "pass": True,
                "score": score,
                "reason": f"matched {hit.get('doc_id')} at rank {rank}",
            }

    observed = [hit.get("doc_id") for hit in hits[:max_rank]]
    return {
        "pass": False,
        "score": 0,
        "reason": (
            f"expected one of {sorted(relevant_doc_ids)} within rank {max_rank}, "
            f"observed {observed}"
        ),
    }


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return [str(item) for item in value]
