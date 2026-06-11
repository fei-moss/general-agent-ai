"""Token aggregation helpers for realtime streaming."""

from __future__ import annotations

import time
from collections.abc import Callable


class TokenAggregator:
    """Flush first token immediately, aggregate subsequent tokens."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] | None = None,
        window_s: float = 0.05,
        max_tokens: int = 8,
    ) -> None:
        self._clock = clock or time.monotonic
        self._window_s = window_s
        self._max_tokens = max_tokens
        self._first_flushed = False
        self._buffer: list[str] = []
        self._last_flush_at = self._clock()

    def push(self, token: str) -> str | None:
        if not token:
            return None
        now = self._clock()
        if not self._first_flushed:
            self._first_flushed = True
            self._last_flush_at = now
            return token
        self._buffer.append(token)
        if len(self._buffer) >= self._max_tokens or now - self._last_flush_at >= self._window_s:
            return self.flush()
        return None

    def flush(self) -> str | None:
        if not self._buffer:
            return None
        out = "".join(self._buffer)
        self._buffer.clear()
        self._last_flush_at = self._clock()
        return out
