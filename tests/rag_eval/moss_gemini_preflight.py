from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import httpx


DEFAULT_MODEL = "gemini-embedding-2"
DEFAULT_DIMENSION = 256
DEFAULT_OUTPUT = Path(".artifacts/release/moss_gemini_preflight.json")
ENDPOINT_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:embedContent"
)


def build_preflight_result(
    *,
    http_status: int,
    payload: dict[str, Any],
    embedding_model: str,
) -> dict[str, Any]:
    """Build a redacted, machine-readable Gemini embedding preflight result."""
    result: dict[str, Any] = {
        "status": "failed",
        "http_status": http_status,
        "embedding_model": embedding_model,
    }

    values = payload.get("embedding", {}).get("values")
    if 200 <= http_status < 300 and isinstance(values, list) and values:
        result["status"] = "passed"
        result["embedding_dimension"] = len(values)
        return result

    error = payload.get("error") if isinstance(payload.get("error"), dict) else {}
    reason, caller_ip, service = _extract_google_error_info(error)
    if reason:
        result["reason"] = reason
    if caller_ip:
        result["caller_ip"] = caller_ip
    if service:
        result["service"] = service
    if error.get("status"):
        result["google_status"] = str(error["status"])
    if error.get("message"):
        result["message"] = str(error["message"])

    if reason == "API_KEY_IP_ADDRESS_BLOCKED" or http_status in {401, 403}:
        result["status"] = "blocked"
    return result


def run_preflight(
    *,
    api_key: str,
    embedding_model: str = DEFAULT_MODEL,
    output_dimension: int = DEFAULT_DIMENSION,
    timeout_s: float = 30.0,
) -> dict[str, Any]:
    """Call Gemini embedding once and return a redacted preflight result."""
    endpoint = ENDPOINT_TEMPLATE.format(model=embedding_model)
    request_payload = {
        "model": f"models/{embedding_model}",
        "content": {"parts": [{"text": "MOSS RAG eval smoke"}]},
        "outputDimensionality": output_dimension,
    }
    try:
        with httpx.Client(timeout=timeout_s) as client:
            response = client.post(
                endpoint,
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": api_key,
                },
                json=request_payload,
            )
        try:
            payload = response.json()
        except json.JSONDecodeError:
            payload = {"error": {"message": response.text[:500]}}
        result = build_preflight_result(
            http_status=response.status_code,
            payload=payload,
            embedding_model=embedding_model,
        )
        if result.get("status") == "passed" and result.get("embedding_dimension") != output_dimension:
            result["status"] = "failed"
            result["reason"] = "EMBEDDING_DIMENSION_MISMATCH"
            result["expected_embedding_dimension"] = output_dimension
        return result
    except httpx.RequestError as exc:
        return {
            "status": "blocked",
            "http_status": None,
            "embedding_model": embedding_model,
            "reason": "REQUEST_ERROR",
            "message": str(exc),
        }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a redacted Gemini embedding preflight for MOSS RAG eval."
    )
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--api-key-env", default="GEMINI_API_KEY")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--dimension", type=int, default=DEFAULT_DIMENSION)
    parser.add_argument("--timeout-s", type=float, default=30.0)
    args = parser.parse_args()

    api_key = os.environ.get(args.api_key_env)
    if not api_key:
        result = {
            "status": "blocked",
            "http_status": None,
            "embedding_model": args.model,
            "reason": "MISSING_GEMINI_API_KEY",
        }
    else:
        result = run_preflight(
            api_key=api_key,
            embedding_model=args.model,
            output_dimension=args.dimension,
            timeout_s=args.timeout_s,
        )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Gemini preflight {result['status']} -> {output_path}")
    if result["status"] != "passed":
        raise SystemExit(1)


def _extract_google_error_info(error: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    for detail in error.get("details") or []:
        if not isinstance(detail, dict):
            continue
        metadata = detail.get("metadata") or {}
        if detail.get("reason") or metadata:
            return (
                detail.get("reason"),
                metadata.get("callerIp"),
                metadata.get("service"),
            )
    return None, None, None


if __name__ == "__main__":
    main()
