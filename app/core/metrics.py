"""Minimal in-process metrics interface.

The default implementation records counters, gauges, and histogram summaries in
process and can render Prometheus text. Tests can still use InMemoryMetrics for
precise assertions.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
import math
import re
from typing import Any


_METRIC_RE = re.compile(r"[^a-zA-Z0-9_:]")
_LABEL_RE = re.compile(r"[^a-zA-Z0-9_]")


@dataclass
class _HistogramSample:
    count: float = 0.0
    total: float = 0.0
    last: float = 0.0


@dataclass
class MetricsRegistry:
    counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = field(
        default_factory=lambda: defaultdict(float)
    )
    gauges: dict[tuple[str, tuple[tuple[str, str], ...]], float] = field(
        default_factory=dict
    )
    histograms: dict[
        tuple[str, tuple[tuple[str, str], ...]], _HistogramSample
    ] = field(default_factory=dict)

    def inc_counter(
        self, name: str, labels: dict[str, str] | None = None, value: float = 1.0
    ) -> None:
        self.counters[(_sanitize_metric_name(name), _labels(labels))] += float(value)

    def set_gauge(
        self, name: str, value: float, labels: dict[str, str] | None = None
    ) -> None:
        self.gauges[(_sanitize_metric_name(name), _labels(labels))] = float(value)

    def observe_histogram(
        self, name: str, value: float, labels: dict[str, str] | None = None
    ) -> None:
        key = (_sanitize_metric_name(name), _labels(labels))
        sample = self.histograms.setdefault(key, _HistogramSample())
        sample.count += 1
        sample.total += float(value)
        sample.last = float(value)

    def render_prometheus(self) -> str:
        lines: list[str] = []
        for (name, labels), value in sorted(self.counters.items()):
            lines.append(_sample_line(name, labels, value))
        for (name, labels), value in sorted(self.gauges.items()):
            lines.append(_sample_line(name, labels, value))
        for (name, labels), sample in sorted(self.histograms.items()):
            lines.append(_sample_line(f"{name}_count", labels, sample.count))
            lines.append(_sample_line(f"{name}_sum", labels, sample.total))
            lines.append(_sample_line(f"{name}_last", labels, sample.last))
        return "\n".join(lines) + ("\n" if lines else "")


_DEFAULT_REGISTRY = MetricsRegistry()


def default_metrics_registry() -> MetricsRegistry:
    return _DEFAULT_REGISTRY


def reset_default_metrics_registry() -> None:
    _DEFAULT_REGISTRY.counters.clear()
    _DEFAULT_REGISTRY.gauges.clear()
    _DEFAULT_REGISTRY.histograms.clear()


class Metrics:
    def __init__(self, registry: MetricsRegistry | None = None) -> None:
        self._registry = registry or default_metrics_registry()

    def observe_ttft(self, seconds: float, labels: dict[str, str]) -> None:
        self.observe_histogram("chat_ttft_seconds", seconds, labels)

    def observe_histogram(
        self, name: str, value: float, labels: dict[str, str] | None = None
    ) -> None:
        self._registry.observe_histogram(name, value, labels)

    def inc_counter(
        self, name: str, labels: dict[str, str] | None = None, value: float = 1.0
    ) -> None:
        self._registry.inc_counter(name, labels, value)

    def set_gauge(
        self, name: str, value: float, labels: dict[str, str] | None = None
    ) -> None:
        self._registry.set_gauge(name, value, labels)

    def render_prometheus(self) -> str:
        return self._registry.render_prometheus()


class InMemoryMetrics(Metrics):
    def __init__(self) -> None:
        # Do not call Metrics.__init__; this fake intentionally stays isolated.
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


def _labels(labels: dict[str, str] | None) -> tuple[tuple[str, str], ...]:
    if not labels:
        return ()
    return tuple(
        sorted(
            (
                _sanitize_label_name(str(key)),
                _sanitize_label_value(str(value)),
            )
            for key, value in labels.items()
        )
    )


def _sanitize_metric_name(name: str) -> str:
    text = _METRIC_RE.sub("_", str(name).strip())
    return text or "metric"


def _sanitize_label_name(name: str) -> str:
    text = _LABEL_RE.sub("_", str(name).strip())
    if not text:
        return "label"
    if text[0].isdigit():
        return f"label_{text}"
    return text


def _sanitize_label_value(value: str) -> str:
    # Label values can contain punctuation, but keep them bounded and escaped.
    return value[:256]


def _sample_line(
    name: str, labels: tuple[tuple[str, str], ...], value: float
) -> str:
    label_text = ""
    if labels:
        pairs = ",".join(f'{key}="{_escape_label(value)}"' for key, value in labels)
        label_text = f"{{{pairs}}}"
    return f"{name}{label_text} {_format_float(value)}"


def _escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _format_float(value: float) -> str:
    if math.isfinite(value):
        return f"{value:.12g}"
    if value > 0:
        return "+Inf"
    if value < 0:
        return "-Inf"
    return "NaN"
