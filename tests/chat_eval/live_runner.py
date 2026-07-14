"""Optional live replay runner for Ask this Agent chat golden cases."""

from __future__ import annotations

import argparse
import http.client
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from tests.chat_eval.evaluator import ChatBehaviorCase, load_cases, load_coverage_contract


DEFAULT_OUTPUT = Path(".artifacts/release/chat_eval_live.json")
_SECRET_PATTERNS = (
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}", re.I),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)
_REAL_EVM_ADDRESS = re.compile(r"\b0x(?!Eval)[a-fA-F0-9]{40}\b")


@dataclass(frozen=True)
class HttpResponse:
    """Small transport response used by live replay tests."""

    status: int
    body: str


TransportPost = Callable[[str, dict[str, str], dict[str, Any], float], HttpResponse]
TransportGet = Callable[[str, dict[str, str], float], HttpResponse]


def select_cases(
    cases: list[ChatBehaviorCase],
    *,
    case_ids: set[str] | None = None,
    tags: set[str] | None = None,
    exclude_tags: set[str] | None = None,
) -> list[ChatBehaviorCase]:
    """Filter cases for live replay."""
    selected = cases
    if case_ids:
        selected = [case for case in selected if case.id in case_ids]
    if tags:
        selected = [
            case
            for case in selected
            if tags.intersection({str(tag) for tag in case.raw.get("tags", [])})
        ]
    if exclude_tags:
        selected = [
            case
            for case in selected
            if not exclude_tags.intersection(
                {str(tag) for tag in case.raw.get("tags", [])}
            )
        ]
    return selected


def build_chat_payload(case: ChatBehaviorCase, dataset_version: str) -> dict[str, Any]:
    """Build the POST /chat body for a golden case."""
    payload: dict[str, Any] = {
        "message": case.user_message,
        "stream": True,
        "metadata": {
            "mode": "eval",
            "task_type": "chat_eval",
            "chat_eval_case_id": case.id,
            "chat_eval_dataset_version": dataset_version,
        },
        "proxy_payload": {},
    }
    fixture_payload = case.raw.get("fixture_proxy_payload")
    if isinstance(fixture_payload, dict):
        payload["proxy_payload"] = fixture_payload
    return payload


def apply_context_overrides(
    payload: dict[str, Any],
    *,
    agent_address: str | None = None,
    chain_id: int | None = None,
    wallet_address: str | None = None,
    drop_chain_id: bool = False,
) -> dict[str, Any]:
    """Apply live-only context overrides without changing fixture files."""
    if not drop_chain_id and not any(
        value is not None for value in (agent_address, chain_id, wallet_address)
    ):
        return payload
    output = dict(payload)
    proxy_payload = dict(output.get("proxy_payload") or {})
    if agent_address:
        proxy_payload["agent_address"] = agent_address
    if drop_chain_id:
        proxy_payload.pop("chain_id", None)
    if chain_id is not None:
        proxy_payload["chain_id"] = chain_id
    if wallet_address:
        proxy_payload["wallet_address"] = wallet_address
    output["proxy_payload"] = proxy_payload
    return output


def apply_marketplace_identity(
    payload: dict[str, Any],
    *,
    marketplace_user_id: str,
    marketplace_wallet: str,
) -> dict[str, Any]:
    """Overlay the server-owned identity required by the Chat boundary."""
    normalized_wallet = marketplace_wallet.strip().lower()
    output = dict(payload)
    proxy_payload = dict(output.get("proxy_payload") or {})
    proxy_payload["marketplace_identity"] = {
        "user_id": marketplace_user_id.strip(),
        "wallet_address": normalized_wallet,
    }
    proxy_payload["user_address"] = normalized_wallet
    proxy_payload["wallet_address"] = normalized_wallet
    output["proxy_payload"] = proxy_payload
    return output


def parse_sse_events(stream_text: str) -> list[dict[str, Any]]:
    """Parse a simple SSE stream into event dictionaries."""
    events: list[dict[str, Any]] = []
    current: dict[str, str] = {}
    for line in stream_text.splitlines():
        if not line.strip():
            if current:
                events.append(_finish_event(current))
                current = {}
            continue
        if line.startswith("event:"):
            current["event"] = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            current["data"] = line.split(":", 1)[1].strip()
        elif line.startswith("id:"):
            current["id"] = line.split(":", 1)[1].strip()
    if current:
        events.append(_finish_event(current))
    return events


def replay_cases(
    cases: list[ChatBehaviorCase],
    *,
    base_url: str,
    marketplace_user_id: str,
    marketplace_wallet: str,
    timeout_s: float = 60.0,
    agent_address: str | None = None,
    chain_id: int | None = None,
    drop_chain_id: bool = False,
    post: TransportPost | None = None,
    get: TransportGet | None = None,
) -> dict[str, Any]:
    """Replay cases against a live API and return a sanitized report."""
    contract = load_coverage_contract()
    post = post or _curl_post
    get = get or _curl_get
    marketplace_user_id = marketplace_user_id.strip()
    marketplace_wallet = marketplace_wallet.strip().lower()
    headers = {
        "Content-Type": "application/json",
        "X-Marketplace-User-ID": marketplace_user_id,
        "X-Marketplace-Wallet": marketplace_wallet,
    }
    base_url = base_url.rstrip("/")
    results: list[dict[str, Any]] = []
    started = time.monotonic()
    for case in cases:
        case_started = time.monotonic()
        payload = build_chat_payload(case, str(contract.get("dataset_version") or ""))
        payload = apply_context_overrides(
            payload,
            agent_address=agent_address,
            chain_id=chain_id,
            drop_chain_id=drop_chain_id,
        )
        payload = apply_marketplace_identity(
            payload,
            marketplace_user_id=marketplace_user_id,
            marketplace_wallet=marketplace_wallet,
        )
        try:
            case_headers = dict(headers)
            case_headers["Idempotency-Key"] = (
                f"chat-eval-{case.id}-{time.time_ns()}"
            )
            chat = post(f"{base_url}/chat", case_headers, payload, timeout_s)
            if not chat.body.strip():
                raise RuntimeError(f"POST /chat returned empty body status={chat.status}")
            chat_body = json.loads(chat.body)
            run_id = str(chat_body.get("agent_run_id") or "")
            stream_url = str(chat_body.get("stream_url") or f"/stream/{run_id}")
            stream = get(f"{base_url}{stream_url}", headers, timeout_s)
            events = parse_sse_events(stream.body)
            results.append(
                _case_result(
                    case,
                    chat_body=chat_body,
                    events=events,
                    stream_status=stream.status,
                    latency_ms=round((time.monotonic() - case_started) * 1000, 2),
                )
            )
        except Exception as exc:
            results.append(
                {
                    "case_id": case.id,
                    "status": "error",
                    "error": sanitize_text(str(exc)),
                    "latency_ms": round((time.monotonic() - case_started) * 1000, 2),
                }
            )
    status = (
        "passed"
        if results and all(result.get("status") == "completed" for result in results)
        else "failed"
    )
    report = {
        "status": status,
        "base_url": base_url,
        "case_count": len(results),
        "duration_ms": round((time.monotonic() - started) * 1000, 2),
        "results": results,
    }
    if not results:
        report["blockers"] = ["no live replay cases selected"]
    return report


def write_report(report: dict[str, Any], output_path: Path) -> None:
    """Write a live replay report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def sanitize_text(value: str) -> str:
    """Redact secrets and real-looking wallet addresses from reports."""
    text = str(value or "")
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub("<redacted-secret>", text)
    text = _REAL_EVM_ADDRESS.sub("<redacted-address>", text)
    return text


def _finish_event(current: dict[str, str]) -> dict[str, Any]:
    data_text = current.get("data", "")
    try:
        data = json.loads(data_text) if data_text else {}
    except json.JSONDecodeError:
        data = {"raw": sanitize_text(data_text)}
    return {
        "id": current.get("id"),
        "event": current.get("event"),
        "data": _sanitize_json(data),
    }


def _case_result(
    case: ChatBehaviorCase,
    *,
    chat_body: dict[str, Any],
    events: list[dict[str, Any]],
    stream_status: int,
    latency_ms: float,
) -> dict[str, Any]:
    content = ""
    tool_calls: list[str] = []
    error_events = 0
    for event in events:
        event_type = event.get("event")
        data = event.get("data") or {}
        if event_type == "TOOL_CALL_STARTED":
            tool_name = (data.get("data") or {}).get("tool_name")
            if tool_name:
                tool_calls.append(str(tool_name))
        if event_type == "ERROR":
            error_events += 1
        if event_type == "RUN_COMPLETED":
            content = str((data.get("data") or {}).get("content") or "")
    completed = bool(content and not error_events)
    error = ""
    if not completed:
        if error_events:
            error = "stream_error_event"
        elif stream_status == 206:
            error = "stream_incomplete"
        else:
            error = "run_completed_missing"
    return {
        "case_id": case.id,
        "status": "completed" if completed else "error",
        "run_id": sanitize_text(str(chat_body.get("agent_run_id") or "")),
        "trace_id": sanitize_text(str(chat_body.get("trace_id") or "")),
        "tool_calls": tool_calls,
        "event_count": len(events),
        "error_events": error_events,
        "error": error or None,
        "content": sanitize_text(content),
        "latency_ms": latency_ms,
    }


def _sanitize_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _sanitize_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_json(item) for item in value]
    if isinstance(value, str):
        return sanitize_text(value)
    return value


def _urllib_post(
    url: str, headers: dict[str, str], body: dict[str, Any], timeout_s: float
) -> HttpResponse:
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            return HttpResponse(
                status=int(response.status),
                body=_read_response_text(response),
            )
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"POST {url} failed: {exc.code} {exc.read().decode('utf-8')}") from exc


def _urllib_get(url: str, headers: dict[str, str], timeout_s: float) -> HttpResponse:
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            return HttpResponse(
                status=int(response.status),
                body=_read_response_text(response),
            )
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"GET {url} failed: {exc.code} {exc.read().decode('utf-8')}") from exc


def _curl_post(
    url: str, headers: dict[str, str], body: dict[str, Any], timeout_s: float
) -> HttpResponse:
    """POST JSON with curl for DockerHost HTTP/2 compatibility."""
    return _run_curl(
        [
            "curl",
            "-sS",
            "--http1.1",
            "--max-time",
            str(timeout_s),
            "-w",
            "\n%{http_code}",
            "-X",
            "POST",
            *[item for key, value in headers.items() for item in ("-H", f"{key}: {value}")],
            "-d",
            "@-",
            url,
        ],
        input_text=json.dumps(body),
        allow_partial=False,
    )


def _curl_get(url: str, headers: dict[str, str], timeout_s: float) -> HttpResponse:
    """GET an SSE stream with curl for DockerHost HTTP/2 compatibility."""
    return _run_curl(
        [
            "curl",
            "-sS",
            "--http1.1",
            "-N",
            "--max-time",
            str(timeout_s),
            "-w",
            "\n%{http_code}",
            *[item for key, value in headers.items() for item in ("-H", f"{key}: {value}")],
            url,
        ],
        input_text=None,
        allow_partial=True,
    )


def _run_curl(
    command: list[str], *, input_text: str | None, allow_partial: bool
) -> HttpResponse:
    completed = subprocess.run(
        command,
        input=input_text,
        capture_output=True,
        text=True,
        check=False,
    )
    stdout = completed.stdout or ""
    body, status = _split_curl_body_status(stdout)
    if completed.returncode != 0 and allow_partial and stdout:
        return HttpResponse(status=206, body=body or stdout)
    if completed.returncode != 0:
        raise RuntimeError(sanitize_text(completed.stderr or stdout or "curl failed"))
    if status >= 400 or status == 0:
        raise RuntimeError(f"HTTP {status}: {sanitize_text(body)}")
    return HttpResponse(status=status, body=body)


def _split_curl_body_status(stdout: str) -> tuple[str, int]:
    body, separator, status_text = stdout.rpartition("\n")
    if separator and status_text.isdigit():
        return body, int(status_text)
    return stdout, 0


def _read_response_text(response: Any) -> str:
    """Read response body while preserving partial SSE data on short reads."""
    try:
        body = response.read()
    except http.client.IncompleteRead as exc:
        body = exc.partial
    return body.decode("utf-8", errors="replace")


def _truthy_env(name: str) -> bool:
    return str(os.environ.get(name) or "").strip().lower() in {"1", "true", "yes", "on"}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument(
        "--marketplace-user-id",
        default=os.environ.get("CHAT_EVAL_MARKETPLACE_USER_ID"),
    )
    parser.add_argument(
        "--marketplace-wallet",
        default=os.environ.get("CHAT_EVAL_MARKETPLACE_WALLET"),
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--timeout-s", type=float, default=60.0)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--tag", action="append", default=[])
    parser.add_argument("--exclude-tag", action="append", default=[])
    parser.add_argument("--agent-address", default=os.environ.get("CHAT_EVAL_AGENT_ADDRESS"))
    parser.add_argument("--chain-id", type=int, default=None)
    parser.add_argument(
        "--drop-chain-id",
        action="store_true",
        default=_truthy_env("CHAT_EVAL_DROP_CHAIN_ID"),
        help="Remove fixture chain_id values for live endpoints that identify agents by address only.",
    )
    parser.add_argument("--strict", action="store_true")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    if not args.marketplace_user_id or not args.marketplace_wallet:
        raise SystemExit(
            "missing Marketplace identity: set CHAT_EVAL_MARKETPLACE_USER_ID and "
            "CHAT_EVAL_MARKETPLACE_WALLET or pass both CLI options"
        )
    cases = select_cases(
        load_cases(),
        case_ids=set(args.case_id) if args.case_id else None,
        tags=set(args.tag) if args.tag else None,
        exclude_tags=set(args.exclude_tag) if args.exclude_tag else None,
    )
    report = replay_cases(
        cases,
        base_url=args.base_url,
        marketplace_user_id=args.marketplace_user_id,
        marketplace_wallet=args.marketplace_wallet,
        timeout_s=args.timeout_s,
        agent_address=args.agent_address,
        chain_id=args.chain_id,
        drop_chain_id=args.drop_chain_id,
    )
    write_report(report, args.output)
    print(f"chat eval live replay {report['status']} -> {args.output}")
    return 1 if args.strict and report["status"] != "passed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
