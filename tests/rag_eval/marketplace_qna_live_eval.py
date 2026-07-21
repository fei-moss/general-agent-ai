"""Live DockerHost acceptance runner for Marketplace QnA retrieval and chat."""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, TypeVar

from tests.chat_eval.live_runner import (
    _curl_get,
    _curl_post,
    apply_marketplace_identity,
    parse_sse_events,
    sanitize_text,
)


EVAL_DIR = Path(__file__).resolve().parent
DEFAULT_RETRIEVAL_OUTPUT = Path(
    ".artifacts/release/marketplace_qna_live_retrieval.json"
)
DEFAULT_CHAT_OUTPUT = Path(".artifacts/release/marketplace_qna_live_chat.json")
DEFAULT_KEYCHAIN_SERVICE = "general-agent-ai-rag-admin-id"
_T = TypeVar("_T")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _normalized(value: str) -> str:
    return "".join(character.casefold() for character in str(value) if character.isalnum())


def _matches_required_alternative(answer: str, alternative: str) -> bool:
    normalized_alternative = _normalized(alternative)
    expected_tokens = re.findall(r"[a-z0-9]+", alternative.casefold())
    segments = re.split(r"[.!?。！？\n]+", answer)
    for segment in segments:
        if normalized_alternative and normalized_alternative in _normalized(segment):
            return True
        if not alternative.isascii() or len(expected_tokens) < 2:
            continue
        answer_tokens = re.findall(r"[a-z0-9]+", segment.casefold())
        cursor = -1
        for expected in expected_tokens:
            start = cursor + 1
            upper_bound = (
                len(answer_tokens)
                if cursor < 0
                else min(len(answer_tokens), start + 4)
            )
            try:
                cursor = answer_tokens.index(expected, start, upper_bound)
            except ValueError:
                break
        else:
            return True
    return False


def evaluate_answer(
    answer: str,
    *,
    required_fact_groups: list[list[str]],
    forbidden_claims: list[str],
) -> dict[str, Any]:
    """Evaluate semantic fact alternatives using deterministic text evidence."""
    group_results = [
        any(_matches_required_alternative(answer, alternative) for alternative in group)
        for group in required_fact_groups
    ]
    normalized_answer = _normalized(answer)
    matched_forbidden = [
        claim
        for claim in forbidden_claims
        if _normalized(claim) and _normalized(claim) in normalized_answer
    ]
    return {
        "passed": bool(group_results)
        and all(group_results)
        and not matched_forbidden,
        "fact_groups": group_results,
        "forbidden_claims": matched_forbidden,
    }


def evaluate_retrieval_response(
    response: dict[str, Any],
    *,
    expected_source_uri: str,
    language: str,
) -> dict[str, Any]:
    """Require a same-language expected source in top five without degradation."""
    matched_rank: int | None = None
    for rank, chunk in enumerate(response.get("chunks") or [], start=1):
        citation = chunk.get("citation") or {}
        metadata = chunk.get("metadata") or {}
        source_uri = str(citation.get("source_uri") or metadata.get("source_uri") or "")
        chunk_language = str(metadata.get("language") or "")
        if source_uri == expected_source_uri and chunk_language == language:
            matched_rank = rank
            break
    degraded = bool(response.get("degraded"))
    return {
        "passed": matched_rank is not None and matched_rank <= 5 and not degraded,
        "matched_rank": matched_rank,
        "degraded": degraded,
    }


def build_chat_payload(*, case_id: str, query: str) -> dict[str, Any]:
    """Build a live chat request that intentionally omits knowledge-base selection."""
    return {
        "message": query,
        "stream": True,
        "metadata": {
            "mode": "eval",
            "task_type": "chat_eval",
            "marketplace_qna_case_id": case_id,
        },
        "proxy_payload": {},
    }


def sanitize_evidence(
    value: Any,
    *,
    sensitive_values: set[str] | None = None,
) -> Any:
    """Recursively redact runtime identities, credentials, and wallet addresses."""
    sensitive_values = {item for item in (sensitive_values or set()) if item}
    if isinstance(value, dict):
        return {
            str(key): sanitize_evidence(item, sensitive_values=sensitive_values)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            sanitize_evidence(item, sensitive_values=sensitive_values) for item in value
        ]
    if isinstance(value, str):
        output = value
        for sensitive in sorted(sensitive_values, key=len, reverse=True):
            output = output.replace(sensitive, "<redacted>")
        return sanitize_text(output)
    return value


def _live_source_uri(document_id: str) -> str:
    parts = document_id.split("_")
    if len(parts) < 4 or not parts[-1].isdigit():
        raise ValueError(f"invalid Marketplace QnA document id: {document_id}")
    language = "cn" if "zh_cn" in document_id else "en"
    return f"urn:moss:marketplace-qna:{language}:{int(parts[-1]):02d}"


def _with_retries(
    operation: Callable[[], _T],
    *,
    attempts: int = 3,
    delay_s: float = 1.0,
) -> _T:
    """Retry transport failures only; semantic evaluation happens afterward."""
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except Exception as exc:  # noqa: BLE001 - bounded live transport boundary
            last_error = exc
            if attempt < attempts:
                time.sleep(delay_s * attempt)
    assert last_error is not None
    raise last_error


def _retrieval_case(
    case: dict[str, Any],
    *,
    base_url: str,
    knowledge_base_id: str,
    admin_id: str,
    timeout_s: float,
) -> dict[str, Any]:
    started = time.monotonic()
    language = "zh-CN" if "zh-CN" in case.get("tags", []) else "en"
    document_id = str(case["relevant_doc_ids"][0])
    expected_source_uri = _live_source_uri(document_id)
    payload = {
        "knowledge_base_id": knowledge_base_id,
        "query": case["query"],
        "top_k": 5,
        "filters": {"language": language},
        "strict": True,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {admin_id}",
    }
    try:
        response = _with_retries(
            lambda: _curl_post(f"{base_url}/rag/query", headers, payload, timeout_s)
        )
        body = json.loads(response.body)
        evaluation = evaluate_retrieval_response(
            body,
            expected_source_uri=expected_source_uri,
            language=language,
        )
        return {
            "case_id": case["id"],
            "http_status": response.status,
            "expected_source_uri": expected_source_uri,
            "expected_language": language,
            **evaluation,
            "latency_ms": round((time.monotonic() - started) * 1000, 2),
        }
    except Exception as exc:  # noqa: BLE001 - report sanitized live failure
        return {
            "case_id": case["id"],
            "passed": False,
            "matched_rank": None,
            "degraded": False,
            "error": sanitize_text(str(exc)),
            "latency_ms": round((time.monotonic() - started) * 1000, 2),
        }


def run_retrieval_eval(
    *,
    base_url: str,
    knowledge_base_id: str,
    admin_id: str,
    timeout_s: float = 30.0,
    workers: int = 4,
) -> dict[str, Any]:
    """Run the complete strict live retrieval fixture."""
    cases = _read_jsonl(EVAL_DIR / "marketplace_qna_golden_queries.jsonl")
    started = time.monotonic()
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = [
            executor.submit(
                _retrieval_case,
                case,
                base_url=base_url.rstrip("/"),
                knowledge_base_id=knowledge_base_id,
                admin_id=admin_id,
                timeout_s=timeout_s,
            )
            for case in cases
        ]
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda row: str(row["case_id"]))
    passed = sum(bool(row.get("passed")) for row in results)
    top1 = sum(row.get("matched_rank") == 1 for row in results)
    degraded = sum(bool(row.get("degraded")) for row in results)
    top1_rate = top1 / len(results) if results else 0.0
    return {
        "schema_version": 1,
        "status": "passed"
        if results
        and passed == len(results)
        and top1_rate >= 0.8
        and degraded == 0
        else "failed",
        "knowledge_base_id": knowledge_base_id,
        "counts": {
            "total": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "top1": top1,
            "degraded": degraded,
        },
        "top1_rate": top1_rate,
        "duration_ms": round((time.monotonic() - started) * 1000, 2),
        "results": results,
    }


def _event_content(events: list[dict[str, Any]]) -> str:
    for event in reversed(events):
        if event.get("event") != "RUN_COMPLETED":
            continue
        data = event.get("data") or {}
        nested = data.get("data") if isinstance(data, dict) else {}
        for candidate in (
            nested.get("content") if isinstance(nested, dict) else None,
            data.get("content") if isinstance(data, dict) else None,
        ):
            if candidate:
                return str(candidate)
    return ""


def collect_stream_events_once(
    url: str,
    headers: dict[str, str],
    timeout_s: float,
    *,
    get: Callable[..., Any] = _curl_get,
) -> list[dict[str, Any]]:
    """Read one bounded SSE window and fall back to durable run state on failure."""
    try:
        response = get(url, headers, timeout_s)
    except Exception:  # noqa: BLE001 - a disconnected SSE is an expected fallback
        return []
    return parse_sse_events(response.body)


def _merge_events(
    first: list[dict[str, Any]], second: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for event in [*first, *second]:
        marker = json.dumps(event, ensure_ascii=False, sort_keys=True)
        if marker not in seen:
            seen.add(marker)
            merged.append(event)
    return merged


def _absolute_stream_url(base_url: str, stream_url: str) -> str:
    if stream_url.startswith(("http://", "https://")):
        return stream_url
    return f"{base_url}{stream_url}"


def _conversation_answer(body: dict[str, Any]) -> str:
    for message in reversed(body.get("messages") or []):
        if str(message.get("role") or "").casefold() == "assistant":
            return str(message.get("content") or "")
    return ""


def _chat_case(
    case: dict[str, Any],
    *,
    base_url: str,
    marketplace_user_id: str,
    marketplace_wallet: str,
    timeout_s: float,
) -> dict[str, Any]:
    started = time.monotonic()
    headers = {
        "Content-Type": "application/json",
        "X-Marketplace-User-ID": marketplace_user_id,
        "X-Marketplace-Wallet": marketplace_wallet,
        "Idempotency-Key": f"marketplace-qna-eval-{case['id']}-{time.time_ns()}",
    }
    payload = apply_marketplace_identity(
        build_chat_payload(case_id=str(case["id"]), query=str(case["query"])),
        marketplace_user_id=marketplace_user_id,
        marketplace_wallet=marketplace_wallet,
    )
    try:
        accepted_response = _with_retries(
            lambda: _curl_post(f"{base_url}/chat", headers, payload, timeout_s)
        )
        accepted = json.loads(accepted_response.body)
        run_id = str(accepted.get("agent_run_id") or "")
        conversation_id = str(accepted.get("conversation_id") or "")
        stream_url = str(accepted.get("stream_url") or f"/stream/{run_id}")
        stream_headers = {
            "X-Marketplace-User-ID": marketplace_user_id,
            "X-Marketplace-Wallet": marketplace_wallet,
        }
        absolute_stream_url = _absolute_stream_url(base_url, stream_url)
        events = collect_stream_events_once(
            absolute_stream_url,
            stream_headers,
            min(timeout_s, 25.0),
        )
        answer = _event_content(events)
        terminal_status = ""
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            run_response = _with_retries(
                lambda: _curl_get(
                    f"{base_url}/runs/{run_id}",
                    stream_headers,
                    min(timeout_s, 20.0),
                ),
                attempts=2,
            )
            run_body = json.loads(run_response.body)
            terminal_status = str(run_body.get("status") or "").upper()
            if terminal_status in {"SUCCEEDED", "FAILED", "CANCELLED"}:
                break
            time.sleep(0.5)
        if not any(event.get("event") == "RUN_COMPLETED" for event in events):
            replay_events = collect_stream_events_once(
                absolute_stream_url,
                stream_headers,
                min(timeout_s, 20.0),
            )
            events = _merge_events(events, replay_events)
            answer = answer or _event_content(events)
        if not answer and conversation_id:
            conversation = _curl_get(
                f"{base_url}/conversations/{conversation_id}",
                stream_headers,
                min(timeout_s, 20.0),
            )
            answer = _conversation_answer(json.loads(conversation.body))
        evaluation = evaluate_answer(
            answer,
            required_fact_groups=case["required_fact_groups"],
            forbidden_claims=case.get("forbidden_claims") or [],
        )
        retrieval_started = any(
            event.get("event") == "RETRIEVAL_STARTED" for event in events
        )
        retrieval_finished = any(
            event.get("event") == "RETRIEVAL_FINISHED" for event in events
        )
        passed = (
            terminal_status == "SUCCEEDED"
            and retrieval_started
            and retrieval_finished
            and evaluation["passed"]
        )
        return {
            "case_id": case["id"],
            "run_id": run_id,
            "terminal_status": terminal_status,
            "retrieval_started": retrieval_started,
            "retrieval_finished": retrieval_finished,
            **evaluation,
            "passed": passed,
            "answer": answer,
            "answer_preview": answer[:400],
            "latency_ms": round((time.monotonic() - started) * 1000, 2),
        }
    except Exception as exc:  # noqa: BLE001 - report sanitized live failure
        return {
            "case_id": case["id"],
            "passed": False,
            "terminal_status": "ERROR",
            "error": sanitize_text(str(exc)),
            "latency_ms": round((time.monotonic() - started) * 1000, 2),
        }


def run_chat_eval(
    *,
    base_url: str,
    marketplace_user_id: str,
    marketplace_wallet: str,
    timeout_s: float = 90.0,
    case_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Run all representative chats through the server-owned default KB."""
    cases = _read_jsonl(EVAL_DIR / "marketplace_qna_chat_cases.jsonl")
    if case_ids:
        cases = [case for case in cases if str(case["id"]) in case_ids]
    started = time.monotonic()
    results: list[dict[str, Any]] = []
    for index, case in enumerate(cases, start=1):
        result = _chat_case(
            case,
            base_url=base_url.rstrip("/"),
            marketplace_user_id=marketplace_user_id,
            marketplace_wallet=marketplace_wallet,
            timeout_s=timeout_s,
        )
        results.append(result)
        print(
            f"[{index:02d}/{len(cases):02d}] {case['id']} "
            f"status={result.get('terminal_status')} passed={result.get('passed')}",
            flush=True,
        )
    passed = sum(bool(result.get("passed")) for result in results)
    return {
        "schema_version": 1,
        "status": "passed" if results and passed == len(results) else "failed",
        "server_default_knowledge_base": True,
        "counts": {
            "total": len(results),
            "passed": passed,
            "failed": len(results) - passed,
        },
        "duration_ms": round((time.monotonic() - started) * 1000, 2),
        "results": results,
    }


def _keychain_admin_id(service: str) -> str:
    completed = subprocess.run(
        ["security", "find-generic-password", "-s", service, "-w"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        raise RuntimeError(f"RAG admin id not found in Keychain service {service}")
    return completed.stdout.strip()


def _write_report(
    report: dict[str, Any],
    path: Path,
    *,
    sensitive_values: set[str],
) -> None:
    sanitized = sanitize_evidence(report, sensitive_values=sensitive_values)
    serialized = json.dumps(sanitized, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    for sensitive in sensitive_values:
        if sensitive and sensitive in serialized:
            raise RuntimeError("sensitive runtime value remained in live evidence")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialized, encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--knowledge-base-id", required=True)
    parser.add_argument("--admin-id", default=os.environ.get("RAG_ADMIN_USER_ID"))
    parser.add_argument("--keychain-service", default=DEFAULT_KEYCHAIN_SERVICE)
    parser.add_argument(
        "--marketplace-user-id", default=os.environ.get("CHAT_EVAL_MARKETPLACE_USER_ID")
    )
    parser.add_argument(
        "--marketplace-wallet", default=os.environ.get("CHAT_EVAL_MARKETPLACE_WALLET")
    )
    parser.add_argument("--retrieval-output", type=Path, default=DEFAULT_RETRIEVAL_OUTPUT)
    parser.add_argument("--chat-output", type=Path, default=DEFAULT_CHAT_OUTPUT)
    parser.add_argument("--retrieval-timeout-s", type=float, default=30.0)
    parser.add_argument("--chat-timeout-s", type=float, default=90.0)
    parser.add_argument("--chat-case-id", action="append", default=[])
    parser.add_argument("--retrieval-workers", type=int, default=4)
    parser.add_argument("--skip-retrieval", action="store_true")
    parser.add_argument("--skip-chat", action="store_true")
    return parser


def _ephemeral_marketplace_identity() -> tuple[str, str]:
    """Generate one valid test identity without persisting it in Git or evidence."""
    user_id = f"marketplace:user:{secrets.randbelow(900_000_000) + 100_000_000}"
    wallet = f"0x{secrets.token_hex(20)}"
    return user_id, wallet


def main() -> int:
    args = _build_parser().parse_args()
    if args.skip_retrieval and args.skip_chat:
        raise SystemExit("both live evaluation phases were skipped")
    admin_id = args.admin_id or _keychain_admin_id(args.keychain_service)
    marketplace_user_id = args.marketplace_user_id
    marketplace_wallet = args.marketplace_wallet
    if not args.skip_chat and not (marketplace_user_id or marketplace_wallet):
        marketplace_user_id, marketplace_wallet = _ephemeral_marketplace_identity()
    elif not args.skip_chat and not (marketplace_user_id and marketplace_wallet):
        raise SystemExit(
            "provide both CHAT_EVAL_MARKETPLACE_USER_ID and "
            "CHAT_EVAL_MARKETPLACE_WALLET, or neither for an ephemeral identity"
        )
    sensitive = {
        admin_id,
        str(marketplace_user_id or ""),
        str(marketplace_wallet or ""),
    }
    statuses: list[str] = []
    if not args.skip_retrieval:
        retrieval = run_retrieval_eval(
            base_url=args.base_url,
            knowledge_base_id=args.knowledge_base_id,
            admin_id=admin_id,
            timeout_s=args.retrieval_timeout_s,
            workers=args.retrieval_workers,
        )
        _write_report(retrieval, args.retrieval_output, sensitive_values=sensitive)
        statuses.append(str(retrieval["status"]))
        print(
            f"Marketplace QnA live retrieval {retrieval['status']}: "
            f"{retrieval['counts']['passed']}/{retrieval['counts']['total']}"
        )
    if not args.skip_chat:
        assert marketplace_user_id and marketplace_wallet
        chat = run_chat_eval(
            base_url=args.base_url,
            marketplace_user_id=marketplace_user_id,
            marketplace_wallet=marketplace_wallet,
            timeout_s=args.chat_timeout_s,
            case_ids=set(args.chat_case_id) if args.chat_case_id else None,
        )
        _write_report(chat, args.chat_output, sensitive_values=sensitive)
        statuses.append(str(chat["status"]))
        print(
            f"Marketplace QnA live chat {chat['status']}: "
            f"{chat['counts']['passed']}/{chat['counts']['total']}"
        )
    return 0 if statuses and all(status == "passed" for status in statuses) else 1


if __name__ == "__main__":
    raise SystemExit(main())
