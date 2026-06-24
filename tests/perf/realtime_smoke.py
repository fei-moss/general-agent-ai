"""In-memory realtime concurrency smoke for TTFT and stream lag evidence."""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic_ai.models.function import FunctionModel

from app.bus.event_bus import InMemoryEventBus, channel_for
from app.core.config import Settings
from app.core.enums import MessageRole
from app.core.events import EventType
from app.runtime.agent_factory import build_agent
from app.runtime.deps import RuntimeDeps
from app.runtime.orchestrator import AgentOrchestrator


@dataclass(frozen=True)
class _RunSample:
    ok: bool
    ttft_ms: float | None
    stream_lag_ms: list[float]
    total_ms: float
    error: str | None = None


async def run_realtime_smoke(
    *,
    requests: int = 50,
    concurrency: int = 10,
    artifact_path: Path | None = None,
) -> dict[str, Any]:
    """Run deterministic concurrent realtime chats and optionally write JSON."""
    if requests <= 0:
        raise ValueError("requests must be positive")
    if concurrency <= 0:
        raise ValueError("concurrency must be positive")
    bus = InMemoryEventBus()
    runtime = RuntimeDeps(
        retriever=_SmokeRetriever(),
        tool_router=_SmokeToolRouter(),
        event_bus=bus,
        message_repo=_SmokeMessageRepo(),
        run_repo=_SmokeRunRepo(),
        settings=Settings(_env_file=None),
    )
    orchestrator = AgentOrchestrator(
        runtime,
        agent=build_agent(FunctionModel(stream_function=_stream_answer)),
    )
    active_runs = 0
    max_active_runs = 0
    active_lock = asyncio.Lock()
    semaphore = asyncio.Semaphore(concurrency)
    started_at = time.perf_counter()

    async def one_run(index: int) -> _RunSample:
        nonlocal active_runs, max_active_runs
        async with semaphore:
            async with active_lock:
                active_runs += 1
                max_active_runs = max(max_active_runs, active_runs)
            try:
                return await _run_and_measure(orchestrator, bus, index)
            finally:
                async with active_lock:
                    active_runs -= 1

    samples = await asyncio.gather(*(one_run(index) for index in range(requests)))
    elapsed_s = time.perf_counter() - started_at
    ok_samples = [sample for sample in samples if sample.ok and sample.ttft_ms is not None]
    ttfts = [sample.ttft_ms for sample in ok_samples if sample.ttft_ms is not None]
    stream_lags = [
        lag
        for sample in ok_samples
        for lag in sample.stream_lag_ms
    ]
    totals = [sample.total_ms for sample in ok_samples]
    report = {
        "mode": "in_memory_mock",
        "requests": requests,
        "concurrency": concurrency,
        "ok": len(ok_samples),
        "errors": requests - len(ok_samples),
        "error_rate": round((requests - len(ok_samples)) / requests, 4),
        "elapsed_s": round(elapsed_s, 4),
        "throughput_rps": round(requests / elapsed_s, 2) if elapsed_s else None,
        "max_active_runs": max_active_runs,
        "ttft_ms": _distribution(ttfts),
        "stream_lag_ms": _distribution(stream_lags),
        "total_ms": _distribution(totals),
        "sample_errors": [
            {"error": sample.error, "total_ms": round(sample.total_ms, 2)}
            for sample in samples
            if not sample.ok
        ][:5],
    }
    if artifact_path is not None:
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return report


async def _run_and_measure(
    orchestrator: AgentOrchestrator,
    bus: InMemoryEventBus,
    index: int,
) -> _RunSample:
    agent_run_id = f"smoke-run-{index}"
    accepted_at = time.time()
    started = time.perf_counter()
    collector = asyncio.create_task(_collect_events(bus, channel_for(agent_run_id)))
    try:
        await orchestrator.run(
            agent_run_id=agent_run_id,
            conversation_id=f"smoke-conv-{index}",
            trace_id=f"smoke-trace-{index}",
            user_message=f"smoke message #{index}",
            accepted_at=accepted_at,
        )
        events = await asyncio.wait_for(collector, timeout=5.0)
        first_token = next(
            (event for event in events if event.type is EventType.TOKEN),
            None,
        )
        if first_token is None:
            return _RunSample(
                ok=False,
                ttft_ms=None,
                stream_lag_ms=[],
                total_ms=(time.perf_counter() - started) * 1000,
                error="missing TOKEN event",
            )
        lags = [max(0.0, (time.time() - event.ts) * 1000) for event in events]
        return _RunSample(
            ok=True,
            ttft_ms=max(0.0, (first_token.ts - accepted_at) * 1000),
            stream_lag_ms=lags,
            total_ms=(time.perf_counter() - started) * 1000,
        )
    except Exception as exc:
        collector.cancel()
        return _RunSample(
            ok=False,
            ttft_ms=None,
            stream_lag_ms=[],
            total_ms=(time.perf_counter() - started) * 1000,
            error=repr(exc),
        )


async def _collect_events(bus: InMemoryEventBus, channel: str) -> list[Any]:
    events: list[Any] = []
    agen = bus.subscribe(channel).__aiter__()
    pending = asyncio.ensure_future(agen.__anext__())
    await asyncio.sleep(0)
    try:
        while True:
            event = await asyncio.wait_for(pending, timeout=5.0)
            events.append(event)
            if event.type is EventType.RUN_COMPLETED:
                return events
            pending = asyncio.ensure_future(agen.__anext__())
    finally:
        pending.cancel()
        await agen.aclose()


async def _stream_answer(_messages, _info):
    answer = (
        "这是一段用于并发 smoke 的安全流式回答, 长度超过尾窗以便立即释放首个安全 token。"
        "它不依赖外部 provider, 只验证本地 orchestrator、事件总线和聚合路径。"
    )
    for index in range(0, len(answer), 18):
        await asyncio.sleep(0.001)
        yield answer[index : index + 18]


def _distribution(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"min": None, "median": None, "p95": None, "max": None}
    ordered = sorted(values)
    return {
        "min": round(ordered[0], 3),
        "median": round(statistics.median(ordered), 3),
        "p95": round(_percentile(ordered, 95), 3),
        "max": round(ordered[-1], 3),
    }


def _percentile(ordered: list[float], percentile: float) -> float:
    index = min(
        len(ordered) - 1,
        int(round((percentile / 100) * (len(ordered) - 1))),
    )
    return ordered[index]


class _SmokeRetriever:
    async def retrieve(self, query: str, top_k: int) -> list[dict[str, Any]]:
        return []


class _SmokeToolRouter:
    async def route(
        self,
        query: str,
        tool_name: str | None = None,
        *,
        agent_run_id: str = "",
    ) -> dict[str, Any]:
        return {"tool_name": tool_name or "noop", "result": {}, "status": "DONE"}


class _SmokeMessageRepo:
    async def list_by_conversation(
        self, conversation_id: str, limit: int
    ) -> list[Any]:
        return []

    async def add(
        self,
        conversation_id: str,
        role: Any,
        content: str,
        token_count: int = 0,
        meta: dict[str, Any] | None = None,
        agent_run_id: str | None = None,
    ) -> dict[str, Any]:
        return {
            "conversation_id": conversation_id,
            "role": role if role is not None else MessageRole.ASSISTANT,
            "content": content,
            "token_count": token_count,
            "agent_run_id": agent_run_id,
        }


class _SmokeRunRepo:
    async def mark_running_with_plan(
        self, agent_run_id: str, intent: Any | None, plan: dict[str, Any]
    ) -> None:
        return None

    async def mark_succeeded_with_answer(
        self,
        agent_run_id: str,
        conversation_id: str,
        answer: str,
        token_count: int,
    ) -> None:
        return None

    async def mark_running(self, agent_run_id: str, intent: Any | None = None) -> None:
        return None

    async def set_plan(self, agent_run_id: str, plan: dict[str, Any]) -> None:
        return None

    async def mark_succeeded(self, agent_run_id: str) -> None:
        return None

    async def mark_failed(self, agent_run_id: str, error: str) -> None:
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Run in-memory realtime smoke")
    parser.add_argument("--requests", type=int, default=50)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument(
        "--artifact-path",
        type=Path,
        default=Path(".artifacts/release/realtime_smoke.json"),
    )
    args = parser.parse_args()
    report = asyncio.run(
        run_realtime_smoke(
            requests=args.requests,
            concurrency=args.concurrency,
            artifact_path=args.artifact_path,
        )
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
