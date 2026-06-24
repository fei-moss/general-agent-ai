"""Lightweight realtime smoke evidence contract tests."""

from __future__ import annotations

import json

from tests.perf.realtime_smoke import run_realtime_smoke


async def test_realtime_smoke_reports_ttft_active_runs_and_stream_lag(tmp_path):
    artifact_path = tmp_path / "realtime_smoke.json"

    report = await run_realtime_smoke(
        requests=12,
        concurrency=4,
        artifact_path=artifact_path,
    )

    assert artifact_path.exists()
    written = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert written == report
    assert report["requests"] == 12
    assert report["concurrency"] == 4
    assert report["ok"] == 12
    assert report["max_active_runs"] >= 2
    assert report["ttft_ms"]["p95"] is not None
    assert report["stream_lag_ms"]["p95"] is not None
