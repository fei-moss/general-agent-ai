from __future__ import annotations

from app.runtime.token_stream import TokenAggregator
from tests.harness_fakes import FakeClock


def test_token_aggregator_flushes_first_token_immediately():
    clock = FakeClock()
    aggregator = TokenAggregator(clock=clock.now, window_s=0.05, max_tokens=3)

    assert aggregator.push("A") == "A"
    assert aggregator.push("B") is None


def test_token_aggregator_flushes_later_tokens_by_count():
    clock = FakeClock()
    aggregator = TokenAggregator(clock=clock.now, window_s=1.0, max_tokens=2)

    assert aggregator.push("A") == "A"
    assert aggregator.push("B") is None
    assert aggregator.push("C") == "BC"


def test_token_aggregator_flushes_later_tokens_by_window():
    clock = FakeClock()
    aggregator = TokenAggregator(clock=clock.now, window_s=0.05, max_tokens=10)

    assert aggregator.push("A") == "A"
    assert aggregator.push("B") is None
    clock.advance(0.06)

    assert aggregator.push("C") == "BC"
