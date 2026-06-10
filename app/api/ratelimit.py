"""基于 redis.asyncio 的滑动窗口限流器。

以 user_id 为维度,在固定时间窗口内统计请求数,超出阈值即拒绝。
采用 Redis sorted set 实现精确滑动窗口:成员为唯一请求标记,score 为
时间戳,按窗口边界裁剪过期成员后统计基数。Redis 不可用时降级为放行
(fail-open),避免限流组件故障导致整体不可用,同时记录告警日志。
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass

from redis.asyncio import Redis

from app.core.logging import get_logger, log_with_fields

logger = get_logger(__name__)

# 滑动窗口长度(秒)
_WINDOW_SECONDS = 60
# Redis key 前缀
_KEY_PREFIX = "ratelimit:"


@dataclass(frozen=True)
class RateLimitResult:
    """一次限流判定的结果。"""

    allowed: bool
    limit: int
    remaining: int
    retry_after: int


class RateLimiter:
    """滑动窗口限流器,key=user_id。"""

    def __init__(
        self, redis: Redis, limit_per_min: int, window_seconds: int = _WINDOW_SECONDS
    ) -> None:
        """注入 redis 客户端与每分钟阈值。"""
        self._redis = redis
        self._limit = max(1, limit_per_min)
        self._window = window_seconds

    async def check(self, user_id: str) -> RateLimitResult:
        """判定指定用户是否允许本次请求。

        使用 Redis pipeline 原子地完成:裁剪过期成员、写入本次标记、
        统计窗口内基数、刷新 TTL。Redis 异常时 fail-open 放行。
        """
        now = time.time()
        key = f"{_KEY_PREFIX}{user_id}"
        window_start = now - self._window
        member = f"{now:.6f}:{uuid.uuid4().hex}"
        try:
            count = await self._run_pipeline(key, window_start, now, member)
        except Exception as exc:  # redis 故障:降级放行
            log_with_fields(
                logger,
                logging.WARNING,
                "限流器降级放行(redis 不可用)",
                user_id=user_id,
                error=str(exc),
            )
            return RateLimitResult(
                allowed=True, limit=self._limit, remaining=self._limit, retry_after=0
            )
        return self._build_result(count)

    async def _run_pipeline(
        self, key: str, window_start: float, now: float, member: str
    ) -> int:
        """执行原子 pipeline,返回当前窗口内的请求计数。"""
        pipe = self._redis.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zadd(key, {member: now})
        pipe.zcard(key)
        pipe.expire(key, self._window + 1)
        results = await pipe.execute()
        # zcard 是第 3 条命令(索引 2)的返回
        return int(results[2])

    def _build_result(self, count: int) -> RateLimitResult:
        """根据计数生成限流结果。"""
        allowed = count <= self._limit
        remaining = max(0, self._limit - count)
        retry_after = 0 if allowed else self._window
        return RateLimitResult(
            allowed=allowed,
            limit=self._limit,
            remaining=remaining,
            retry_after=retry_after,
        )
