"""Minimal metrics interface.

The default implementation is no-op safe. Tests can use InMemoryMetrics, and a
Prometheus/OTel exporter can implement the same methods later.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any


class Metrics:
    def observe_ttft(self, seconds: float, labels: dict[str, str]) -> None:
        self.observe_histogram("chat_ttft_seconds", seconds, labels)

    def observe_histogram(
        self, name: str, value: float, labels: dict[str, str] | None = None
    ) -> None:
        return None

    def inc_counter(
        self, name: str, labels: dict[str, str] | None = None, value: float = 1.0
    ) -> None:
        return None

    def set_gauge(
        self, name: str, value: float, labels: dict[str, str] | None = None
    ) -> None:
        return None


class InMemoryMetrics(Metrics):
    def __init__(self) -> None:
        self.histograms: dict[str, list[tuple[float, dict[str, str]]]] = defaultdict(list)
        self.counters: dict[str, list[tuple[float, dict[str, str]]]] = defaultdict(list)
        self.gauges: dict[str, list[tuple[float, dict[str, str]]]] = defaultdict(list)

    def observe_histogram(
        self, name: str, value: float, labels: dict[str, str] | None = None
    ) -> None:
        self.histograms[name].append((value, labels or {}))

    def inc_counter(
        self, name: str, labels: dict[str, str] | None = None, value: float = 1.0
    ) -> None:
        self.counters[name].append((value, labels or {}))

    def set_gauge(
        self, name: str, value: float, labels: dict[str, str] | None = None
    ) -> None:
        self.gauges[name].append((value, labels or {}))
