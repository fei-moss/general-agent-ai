from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OBS_DIR = ROOT / "ops/observability"
DASHBOARD = OBS_DIR / "chat_server_overview_dashboard.json"
ALERT_RULES = OBS_DIR / "chat_server_alert_rules.yml"
VALIDATOR = ROOT / "scripts/validate_observability_assets.py"


def _dashboard() -> dict:
    return json.loads(DASHBOARD.read_text(encoding="utf-8"))


def _alert_rules_text() -> str:
    return ALERT_RULES.read_text(encoding="utf-8")


def test_dashboard_json_has_required_panels_and_prometheus_queries():
    dashboard = _dashboard()

    assert dashboard["title"] == "Chat Server Observability"
    assert dashboard["schemaVersion"] >= 36
    assert dashboard["uid"] == "chat-server-observability"

    panels = dashboard["panels"]
    titles = {panel["title"] for panel in panels}
    required_titles = {
        "Request rate",
        "API error rate",
        "TTFT p95",
        "Stream token gap p95",
        "Provider 429 and 5xx",
        "Celery queue health",
        "Reaper recovery",
        "Readiness checks",
    }
    assert required_titles <= titles

    text = json.dumps(dashboard, sort_keys=True)
    required_metrics = [
        "chat_requests_total",
        "chat_ttft_seconds",
        "chat_stream_token_gap_seconds",
        "provider_errors_total",
        "provider_rate_limit_decisions_total",
        "celery_queue_depth",
        "celery_oldest_queued_age_seconds",
        "reaper_runs_total",
        "reaper_failed_total",
        "chat_readyz_check",
    ]
    for metric in required_metrics:
        assert metric in text

    for panel in panels:
        targets = panel.get("targets", [])
        assert targets, panel["title"]
        for target in targets:
            assert target.get("expr"), panel["title"]


def test_alert_rules_yaml_declares_required_alerts_and_runbook_annotations():
    text = _alert_rules_text()

    assert "groups:" in text
    assert "name: chat-server-observability" in text

    required_alerts = [
        "ChatServerReadinessDown",
        "ChatServerHighApiErrorRate",
        "ChatServerTTFTTooHigh",
        "ChatServerStreamTokenGapTooHigh",
        "ChatServerProvider429Spike",
        "ChatServerProvider5xxElevated",
        "ChatServerCeleryQueueBacklog",
        "ChatServerReaperStalled",
        "ChatServerMetricsScrapeStale",
    ]
    for alert in required_alerts:
        assert re.search(rf"alert:\s*{alert}\b", text), alert

    required_fragments = [
        "severity: p0",
        "severity: p1",
        "severity: p2",
        "runbook_url:",
        "docs/OBSERVABILITY_AND_ALERTING_RUNBOOK.md",
        "for: 2m",
        "for: 5m",
        "for: 10m",
        "chat_requests_total",
        "chat_ttft_seconds",
        "chat_stream_token_gap_seconds",
        "provider_errors_total",
        "provider_rate_limit_decisions_total",
        "celery_oldest_queued_age_seconds",
        "reaper_runs_total",
        "chat_readyz_check",
    ]
    for fragment in required_fragments:
        assert fragment in text


def test_validator_accepts_committed_observability_assets():
    completed = subprocess.run(
        [sys.executable, str(VALIDATOR)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "validated observability assets" in completed.stdout


def test_validator_rejects_secret_like_literals_in_assets(tmp_path):
    temp_root = tmp_path / "repo"
    temp_obs = temp_root / "ops/observability"
    temp_obs.mkdir(parents=True)
    shutil.copy2(ALERT_RULES, temp_obs / ALERT_RULES.name)

    dashboard = _dashboard()
    dashboard["panels"][0]["targets"][0]["expr"] = 'up{api_key="sk-test-secret"}'
    (temp_obs / DASHBOARD.name).write_text(
        json.dumps(dashboard, indent=2),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, str(VALIDATOR), "--root", str(temp_root)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode != 0
    assert "secret-like" in completed.stdout + completed.stderr
