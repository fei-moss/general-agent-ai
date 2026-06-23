from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs/specifications/2026-06-23-chat-server-observability-alerting-specification.md"
PLAN = ROOT / "docs/implementation-plans/2026-06-23-chat-server-observability-alerting-implementation-plan.md"
RUNBOOK = ROOT / "docs/OBSERVABILITY_AND_ALERTING_RUNBOOK.md"
DASHBOARD = ROOT / "ops/observability/chat_server_overview_dashboard.json"
ALERT_RULES = ROOT / "ops/observability/chat_server_alert_rules.yml"
VALIDATOR = ROOT / "scripts/validate_observability_assets.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_spec_declares_stable_contract_and_required_sections():
    text = _read(SPEC)

    required_terms = [
        "Spec ID: `SPEC-CHAT-OBSERVABILITY-ALERTING-001`",
        "Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`",
        "External requirements",
        "Runtime metrics",
        "Log queries",
        "Alert thresholds",
        "Diagnostic flow",
        "Secret redaction boundary",
        "`SPEC-PROD-READINESS-001`",
        "`SPEC-PROVIDER-GUARDRAILS-001`",
    ]

    for term in required_terms:
        assert term in text


def test_plan_references_spec_and_delivery_scope():
    text = _read(PLAN)

    required_terms = [
        "SPEC-CHAT-OBSERVABILITY-ALERTING-001",
        "Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`",
        "docs/specifications/2026-06-23-chat-server-observability-alerting-specification.md",
        "docs/OBSERVABILITY_AND_ALERTING_RUNBOOK.md",
        "tests/test_observability_alerting_runbook_contract.py",
        "ops/observability/chat_server_overview_dashboard.json",
        "ops/observability/chat_server_alert_rules.yml",
        "scripts/validate_observability_assets.py",
        "tests/test_observability_assets.py",
        "Test Plan",
        "Release And Rollback Risk",
        "Do not modify `dockerhost/` files",
    ]

    for term in required_terms:
        assert term in text


def test_runbook_documents_grafana_mcp_bounded_log_queries():
    text = _read(RUNBOOK)

    required_terms = [
        "https://grafana-mcp.openclaw-ai.cc",
        "不要打印 token",
        "POST /v1/logs",
        "source",
        "service",
        "env",
        "time",
        "limit",
        "line_redacted",
        "GET /v1/logs/tail",
        "broad LogQL",
    ]

    for term in required_terms:
        assert term in text


def test_runbook_covers_panels_alerts_diagnostics_and_redaction():
    text = _read(RUNBOOK)

    required_terms = [
        "请求量",
        "错误率",
        "TTFT",
        "流式 token gap",
        "provider 429/5xx",
        "Celery 队列",
        "reaper",
        "告警规则",
        "readiness 失败",
        "API 错误率升高",
        "provider 429/5xx",
        "疑似 secret 泄漏",
        "不得包含 token",
        "raw Authorization header",
        "ops/observability/chat_server_overview_dashboard.json",
        "ops/observability/chat_server_alert_rules.yml",
        "scripts/validate_observability_assets.py",
    ]

    for term in required_terms:
        assert term in text


def test_spec_plan_and_runbook_document_asset_validation_commands():
    combined = "\n".join([_read(SPEC), _read(PLAN), _read(RUNBOOK)])

    required_terms = [
        "ops/observability/chat_server_overview_dashboard.json",
        "ops/observability/chat_server_alert_rules.yml",
        "scripts/validate_observability_assets.py",
        "tests/test_observability_assets.py",
        ".venv/bin/python scripts/validate_observability_assets.py",
        ".venv/bin/python -m pytest tests/test_observability_alerting_runbook_contract.py tests/test_observability_assets.py -q",
    ]

    for term in required_terms:
        assert term in combined


def test_documents_are_non_empty_and_do_not_embed_obvious_secrets():
    docs = {
        "spec": _read(SPEC),
        "plan": _read(PLAN),
        "runbook": _read(RUNBOOK),
    }

    for name, text in docs.items():
        assert len(text) > 3000, name

    combined = "\n".join(docs.values())
    forbidden_fragments = [
        "Bearer eyJ",
        "sk-",
        "BEGIN PRIVATE KEY",
        "ENVCTL_TOKEN=",
        "GRAFANA_MCP_TOKEN=",
        "OBS_MCP_TOKEN_BTCFUN_TEST=",
        "OBS_MCP_TOKEN_MERLINCHAIN_TEST=",
    ]

    for fragment in forbidden_fragments:
        assert fragment not in combined


def test_expected_observability_asset_paths_are_reserved_for_this_slice():
    assert str(DASHBOARD.relative_to(ROOT)) == "ops/observability/chat_server_overview_dashboard.json"
    assert str(ALERT_RULES.relative_to(ROOT)) == "ops/observability/chat_server_alert_rules.yml"
    assert str(VALIDATOR.relative_to(ROOT)) == "scripts/validate_observability_assets.py"
