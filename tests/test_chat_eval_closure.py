"""Tests for the Ask this Agent chat eval closure tooling."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from tests.chat_eval import live_runner
from tests.chat_eval.evaluator import load_cases, load_coverage_contract
from tests.chat_eval.live_runner import (
    HttpResponse,
    apply_context_overrides,
    build_chat_payload,
    parse_sse_events,
    replay_cases,
    sanitize_text,
    select_cases,
)
from tests.chat_eval.sample_ingestion import (
    candidate_case_from_sample,
    sanitize_sample,
)
from tests.chat_eval.scorecard import build_scorecard, write_scorecard

_MARKETPLACE_USER = "marketplace:user:7"
_MARKETPLACE_WALLET = "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd"


def test_build_chat_payload_uses_proxy_payload_and_eval_metadata():
    contract = load_coverage_contract()
    case = next(
        case for case in load_cases() if case.id == "allow_marketplace_wallet_pnl_context_zh"
    )

    payload = build_chat_payload(case, str(contract["dataset_version"]))

    assert payload["message"] == case.user_message
    assert payload["stream"] is True
    assert payload["metadata"]["task_type"] == "chat_eval"
    assert payload["metadata"]["chat_eval_case_id"] == case.id
    assert payload["proxy_payload"]["wallet_address"].startswith("0xEval")


def test_context_overrides_apply_live_agent_without_mutating_fixture_payload():
    case = next(
        case for case in load_cases() if case.id == "allow_marketplace_wallet_pnl_context_zh"
    )
    payload = build_chat_payload(case, "dataset")
    original = dict(payload["proxy_payload"])

    updated = apply_context_overrides(
        payload,
        agent_address="0x17B09FC949f031dbD540D4caDE59805A08Ee5043",
        chain_id=1,
        wallet_address="0xEvalWalletOverride",
    )

    assert payload["proxy_payload"] == original
    assert updated["proxy_payload"]["agent_address"] == "0x17B09FC949f031dbD540D4caDE59805A08Ee5043"
    assert updated["proxy_payload"]["chain_id"] == 1
    assert updated["proxy_payload"]["wallet_address"] == "0xEvalWalletOverride"


def test_context_overrides_can_drop_synthetic_chain_id_for_live_replay():
    case = next(
        case for case in load_cases() if case.id == "allow_marketplace_wallet_pnl_context_zh"
    )
    payload = build_chat_payload(case, "dataset")

    updated = apply_context_overrides(
        payload,
        agent_address="0x17B09FC949f031dbD540D4caDE59805A08Ee5043",
        drop_chain_id=True,
    )

    assert "chain_id" not in updated["proxy_payload"]
    assert payload["proxy_payload"]["chain_id"] == 1


def test_parse_sse_events_extracts_tool_and_completion_payloads():
    stream = "\n".join(
        [
            "id: 1-0",
            "event: TOOL_CALL_STARTED",
            'data: {"data":{"tool_name":"marketplace_agent_context"}}',
            "",
            "id: 2-0",
            "event: RUN_COMPLETED",
            'data: {"data":{"content":"# Ask this Agent"}}',
            "",
        ]
    )

    events = parse_sse_events(stream)

    assert events[0]["event"] == "TOOL_CALL_STARTED"
    assert events[0]["data"]["data"]["tool_name"] == "marketplace_agent_context"
    assert events[1]["event"] == "RUN_COMPLETED"
    assert events[1]["data"]["data"]["content"] == "# Ask this Agent"


def test_live_replay_uses_transport_and_redacts_sensitive_values():
    case = next(case for case in load_cases() if case.id == "allow_identity_self_intro_zh")
    seen: dict[str, object] = {}

    def post(_url, headers, body, _timeout_s):
        seen["post_headers"] = headers
        seen["post_body"] = body
        return HttpResponse(
            status=202,
            body=json.dumps(
                {
                    "agent_run_id": "run_1234567890abcdef1234567890abcdef",
                    "trace_id": "trace_1234567890abcdef1234567890abcdef",
                    "stream_url": "/stream/run_1234567890abcdef1234567890abcdef",
                }
            ),
        )

    def get(_url, headers, _timeout_s):
        seen["get_headers"] = headers
        return HttpResponse(
            status=200,
            body=(
                "event: RUN_COMPLETED\n"
                'data: {"data":{"content":"wallet 0x1234567890abcdef1234567890abcdef12345678"}}\n\n'
            ),
        )

    report = replay_cases(
        [case],
        base_url="https://example.test",
        marketplace_user_id=f"  {_MARKETPLACE_USER}  ",
        marketplace_wallet="  0xAbCdEfAbCdEfAbCdEfAbCdEfAbCdEfAbCdEfAbCd  ",
        post=post,
        get=get,
    )

    assert report["status"] == "passed"
    assert report["suite_mode"] == "full_suite"
    assert report["suite_id"].startswith("suite_")
    result = report["results"][0]
    assert result["suite_id"] == report["suite_id"]
    assert result["status"] == "completed"
    assert "<redacted-address>" in result["content"]
    assert "0x1234567890abcdef1234567890abcdef12345678" not in json.dumps(report)
    expected_headers = {
        "Content-Type": "application/json",
        "X-Marketplace-User-ID": _MARKETPLACE_USER,
        "X-Marketplace-Wallet": _MARKETPLACE_WALLET,
    }
    assert {
        key: seen["post_headers"][key]
        for key in expected_headers
    } == expected_headers
    assert seen["post_headers"]["Idempotency-Key"].startswith(
        "chat-eval-allow_identity_self_intro_zh-"
    )
    assert seen["get_headers"] == expected_headers
    proxy_payload = seen["post_body"]["proxy_payload"]
    assert proxy_payload["marketplace_identity"] == {
        "user_id": _MARKETPLACE_USER,
        "wallet_address": _MARKETPLACE_WALLET,
    }
    assert proxy_payload["user_address"] == _MARKETPLACE_WALLET
    assert proxy_payload["wallet_address"] == _MARKETPLACE_WALLET


def test_live_case_selection_supports_case_id_and_tag_filters():
    cases = load_cases()

    selected = select_cases(
        cases,
        case_ids={"allow_identity_self_intro_zh"},
        tags={"identity"},
    )

    assert [case.id for case in selected] == ["allow_identity_self_intro_zh"]


def test_live_case_selection_supports_excluding_legacy_tags():
    cases = load_cases()

    selected = select_cases(cases, exclude_tags={"legacy_moss"})

    assert selected
    assert all("legacy_moss" not in case.raw.get("tags", []) for case in selected)
    assert any(case.id == "allow_moss_copy_trading_question_zh" for case in cases)
    assert all(case.id != "allow_moss_copy_trading_question_zh" for case in selected)


def test_live_replay_fails_when_no_cases_are_selected():
    report = replay_cases(
        [],
        base_url="https://example.test",
        marketplace_user_id=_MARKETPLACE_USER,
        marketplace_wallet=_MARKETPLACE_WALLET,
        post=lambda *_args: HttpResponse(status=202, body="{}"),
        get=lambda *_args: HttpResponse(status=200, body=""),
    )

    assert report["status"] == "failed"
    assert report["case_count"] == 0
    assert report["blockers"] == ["no live replay cases selected"]


def test_live_replay_marks_partial_stream_without_completion_as_incomplete():
    case = next(case for case in load_cases() if case.id == "allow_identity_self_intro_zh")

    def post(_url, _headers, _body, _timeout_s):
        return HttpResponse(
            status=202,
            body=json.dumps(
                {
                    "agent_run_id": "run_1234567890abcdef1234567890abcdef",
                    "trace_id": "trace_1234567890abcdef1234567890abcdef",
                    "stream_url": "/stream/run_1234567890abcdef1234567890abcdef",
                }
            ),
        )

    def get(_url, _headers, _timeout_s):
        return HttpResponse(status=206, body="event: LLM_GENERATING\ndata: {}\n\n")

    report = replay_cases(
        [case],
        base_url="https://example.test",
        marketplace_user_id=_MARKETPLACE_USER,
        marketplace_wallet=_MARKETPLACE_WALLET,
        post=post,
        get=get,
    )

    assert report["status"] == "failed"
    assert report["results"][0]["error"] == "stream_incomplete"


def test_curl_timeout_with_partial_sse_is_classified_as_partial(monkeypatch):
    def fake_run(*_args, **_kwargs):
        return SimpleNamespace(
            returncode=28,
            stdout="event: LLM_GENERATING\ndata: {}\n\n200",
            stderr="operation timed out",
        )

    monkeypatch.setattr(live_runner.subprocess, "run", fake_run)

    response = live_runner._run_curl(
        ["curl", "https://example.test/stream/run_1"],
        input_text=None,
        allow_partial=True,
    )

    assert response.status == 206
    assert "LLM_GENERATING" in response.body


def test_curl_transport_uses_http11_for_dockerhost_streams(monkeypatch):
    commands: list[list[str]] = []

    def fake_run_curl(command, *, input_text, allow_partial):
        commands.append(command)
        return HttpResponse(status=200, body="{}")

    monkeypatch.setattr(live_runner, "_run_curl", fake_run_curl)

    live_runner._curl_post(
        "https://example.test/chat",
        {
            "X-Marketplace-User-ID": _MARKETPLACE_USER,
            "X-Marketplace-Wallet": _MARKETPLACE_WALLET,
        },
        {"message": "hi"},
        10,
    )
    live_runner._curl_get(
        "https://example.test/stream/run_1",
        {
            "X-Marketplace-User-ID": _MARKETPLACE_USER,
            "X-Marketplace-Wallet": _MARKETPLACE_WALLET,
        },
        10,
    )

    assert all("--http1.1" in command for command in commands)


def test_sanitize_text_redacts_bearer_tokens_and_real_addresses():
    text = sanitize_text(
        "Bearer alice.internal 0x1234567890abcdef1234567890abcdef12345678"
    )

    assert "<redacted-secret>" in text
    assert "<redacted-address>" in text


def test_sample_ingestion_sanitizes_online_bad_sample():
    sample = {
        "user_message": "查 0x1234567890abcdef1234567890abcdef12345678 的 PnL",
        "assistant_answer": "Bearer alice.internal",
        "failure_reason": "model exposed wallet context",
        "area": "marketplace_data",
        "tags": ["wallet_context"],
    }

    sanitized = sanitize_sample(sample)
    candidate = candidate_case_from_sample(sample)

    assert sanitized["user_message"] == "查 <redacted-address> 的 PnL"
    assert "<redacted-secret>" in sanitized["assistant_answer"]
    assert candidate["id"].startswith("candidate_")
    assert candidate["user_message"] == "查 <redacted-address> 的 PnL"
    assert "online_sample" in candidate["tags"]


def test_scorecard_passes_contract_and_writes_artifact(tmp_path):
    report = asyncio.run(build_scorecard())
    output = tmp_path / "chat_eval_scorecard.json"

    write_scorecard(report, output)

    assert report["status"] == "passed"
    assert report["metadata"]["contract_id"].startswith(
        "SPEC-ASK-THIS-AGENT-CHAT-EVAL-CLOSURE-001"
    )
    assert report["summary"]["forbidden_claim_hits"] == 0
    assert report["summary"]["data_faithfulness_pass_rate"] == 1.0
    assert output.exists()


def test_scorecard_reports_threshold_blockers_when_contract_is_stricter():
    contract = load_coverage_contract()
    contract["release_thresholds"] = dict(contract["release_thresholds"])
    contract["release_thresholds"]["min_trait_hit_rate"] = 1.01

    report = asyncio.run(build_scorecard(contract=contract))

    assert report["status"] == "failed"
    assert any("trait_hit_rate" in blocker for blocker in report["blockers"])


def test_makefile_and_release_gate_expose_chat_eval_commands():
    makefile = Path("Makefile").read_text(encoding="utf-8")
    release = Path("scripts/check_project_release.sh").read_text(encoding="utf-8")

    assert "chat-eval:" in makefile
    assert "chat-eval-report:" in makefile
    assert "chat-eval-live:" in makefile
    assert "CHAT_EVAL_MARKETPLACE_USER_ID" in makefile
    assert "CHAT_EVAL_MARKETPLACE_WALLET" in makefile
    assert "CHAT_EVAL_AUTH_TOKEN" not in makefile
    assert "chat_behavior_eval" in release
    assert "chat_eval_scorecard" in release
