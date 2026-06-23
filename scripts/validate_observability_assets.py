#!/usr/bin/env python3
"""Validate committed observability assets without external dependencies."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


DASHBOARD_PATH = Path("ops/observability/chat_server_overview_dashboard.json")
ALERT_RULES_PATH = Path("ops/observability/chat_server_alert_rules.yml")

REQUIRED_PANEL_TITLES = {
    "Request rate",
    "API error rate",
    "TTFT p95",
    "Stream token gap p95",
    "Provider 429 and 5xx",
    "Celery queue health",
    "Reaper recovery",
    "Readiness checks",
}

REQUIRED_DASHBOARD_METRICS = {
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
}

REQUIRED_ALERTS = {
    "ChatServerReadinessDown",
    "ChatServerHighApiErrorRate",
    "ChatServerTTFTTooHigh",
    "ChatServerStreamTokenGapTooHigh",
    "ChatServerProvider429Spike",
    "ChatServerProvider5xxElevated",
    "ChatServerCeleryQueueBacklog",
    "ChatServerReaperStalled",
    "ChatServerMetricsScrapeStale",
}

REQUIRED_ALERT_METRICS = {
    "chat_requests_total",
    "chat_ttft_seconds",
    "chat_stream_token_gap_seconds",
    "provider_errors_total",
    "provider_rate_limit_decisions_total",
    "celery_oldest_queued_age_seconds",
    "reaper_runs_total",
    "chat_readyz_check",
}

SECRET_PATTERNS = [
    ("private key", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
    ("bearer token", re.compile(r"Bearer\s+(?!<)[A-Za-z0-9._~+/\-]{12,}")),
    ("api key", re.compile(r"\b(?:sk|xox[baprs]?|gh[pousr])-[A-Za-z0-9_\-]{6,}")),
    (
        "token assignment",
        re.compile(
            r"\b(?:ENVCTL_TOKEN|GRAFANA_MCP_TOKEN|OBS_MCP_TOKEN_[A-Z0-9_]+)"
            r"\s*[:=]\s*['\"]?[A-Za-z0-9._~+/\-]{4,}"
        ),
    ),
    (
        "inline credential",
        re.compile(
            r"\b(?:api[_-]?key|secret|password|token)\s*[:=]\s*"
            r"['\"](?!<|\$)[^'\"\s]{8,}['\"]",
            re.IGNORECASE,
        ),
    ),
]


class ValidationError(Exception):
    pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root. Defaults to this script's parent repository.",
    )
    args = parser.parse_args(argv)

    root = args.root.resolve()
    errors: list[str] = []
    try:
        validate_assets(root)
    except ValidationError as exc:
        errors.extend(str(exc).splitlines())

    if errors:
        for error in errors:
            print(f"observability asset validation error: {error}", file=sys.stderr)
        return 1

    print("validated observability assets: dashboard and alert rules")
    return 0


def validate_assets(root: Path) -> None:
    dashboard_path = root / DASHBOARD_PATH
    alert_rules_path = root / ALERT_RULES_PATH
    errors: list[str] = []

    for path in (dashboard_path, alert_rules_path):
        if not path.exists():
            errors.append(f"missing required asset: {path.relative_to(root)}")

    if not errors:
        dashboard_text = dashboard_path.read_text(encoding="utf-8")
        alert_rules_text = alert_rules_path.read_text(encoding="utf-8")
        errors.extend(_secret_hygiene_errors(dashboard_path, dashboard_text, root))
        errors.extend(_secret_hygiene_errors(alert_rules_path, alert_rules_text, root))
        errors.extend(_validate_dashboard(dashboard_text))
        errors.extend(_validate_alert_rules(alert_rules_text))

    if errors:
        raise ValidationError("\n".join(errors))


def _validate_dashboard(text: str) -> list[str]:
    errors: list[str] = []
    try:
        dashboard = json.loads(text)
    except json.JSONDecodeError as exc:
        return [f"dashboard JSON is invalid: {exc}"]

    if not isinstance(dashboard, dict):
        return ["dashboard root must be a JSON object"]

    if dashboard.get("title") != "Chat Server Observability":
        errors.append("dashboard title must be 'Chat Server Observability'")
    if dashboard.get("uid") != "chat-server-observability":
        errors.append("dashboard uid must be 'chat-server-observability'")
    if int(dashboard.get("schemaVersion") or 0) < 36:
        errors.append("dashboard schemaVersion must be >= 36")

    panels = dashboard.get("panels")
    if not isinstance(panels, list) or not panels:
        errors.append("dashboard must define non-empty panels")
        panels = []

    titles = {panel.get("title") for panel in panels if isinstance(panel, dict)}
    missing_titles = sorted(REQUIRED_PANEL_TITLES - titles)
    if missing_titles:
        errors.append(f"dashboard missing required panels: {', '.join(missing_titles)}")

    for panel in panels:
        if not isinstance(panel, dict):
            errors.append("dashboard panel must be an object")
            continue
        title = str(panel.get("title") or "<untitled>")
        targets = panel.get("targets")
        if not isinstance(targets, list) or not targets:
            errors.append(f"dashboard panel has no targets: {title}")
            continue
        for target in targets:
            if not isinstance(target, dict) or not str(target.get("expr") or "").strip():
                errors.append(f"dashboard panel target missing expr: {title}")

    missing_metrics = sorted(
        metric for metric in REQUIRED_DASHBOARD_METRICS if metric not in text
    )
    if missing_metrics:
        errors.append(
            "dashboard missing required metric mentions: " + ", ".join(missing_metrics)
        )

    return errors


def _validate_alert_rules(text: str) -> list[str]:
    errors: list[str] = []
    if "groups:" not in text:
        errors.append("alert rules must include groups")
    if "name: chat-server-observability" not in text:
        errors.append("alert rules must include chat-server-observability group")

    alert_blocks = _alert_blocks(text)
    missing_alerts = sorted(REQUIRED_ALERTS - set(alert_blocks))
    if missing_alerts:
        errors.append(f"alert rules missing alerts: {', '.join(missing_alerts)}")

    for alert_name, body in alert_blocks.items():
        for field in ("expr:", "for:", "labels:", "severity:", "annotations:", "runbook_url:"):
            if field not in body:
                errors.append(f"alert {alert_name} missing {field}")
        if "SPEC-CHAT-OBSERVABILITY-ALERTING-001" not in body:
            errors.append(f"alert {alert_name} missing spec_id label")

    missing_metrics = sorted(
        metric for metric in REQUIRED_ALERT_METRICS if metric not in text
    )
    if missing_metrics:
        errors.append(
            "alert rules missing required metric mentions: " + ", ".join(missing_metrics)
        )

    return errors


def _alert_blocks(text: str) -> dict[str, str]:
    pattern = re.compile(
        r"(?ms)^\s*-\s+alert:\s*(?P<name>[A-Za-z0-9_]+)\b(?P<body>.*?)(?=^\s*-\s+alert:|\Z)"
    )
    return {match.group("name"): match.group("body") for match in pattern.finditer(text)}


def _secret_hygiene_errors(path: Path, text: str, root: Path) -> list[str]:
    errors: list[str] = []
    rel = path.relative_to(root)
    for label, pattern in SECRET_PATTERNS:
        match = pattern.search(text)
        if match:
            line = text.count("\n", 0, match.start()) + 1
            errors.append(f"secret-like {label} literal in {rel}:{line}")
    return errors


if __name__ == "__main__":
    raise SystemExit(main())
