"""LLM 路由与韧性封装。

LLMRouter 按配置选择具体 Provider,并提供带超时、指数退避重试、以及
失败后降级到内置 MockLLMProvider 的健壮调用入口,保证链路在外部模型
不可用时仍可返回结果。
"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator

from app.core.config import Settings, get_settings
from app.core.enums import IntentType
from app.core.interfaces import LLMProvider
from app.core.logging import get_logger
from app.llm.providers import (
    AnthropicProvider,
    MockLLMProvider,
    OpenAICompatProvider,
    ZAICompatProvider,
)

logger = get_logger(__name__)

# 重试默认参数
_DEFAULT_MAX_RETRIES = 2
_DEFAULT_BASE_DELAY_S = 0.5
_DEFAULT_MAX_DELAY_S = 8.0


def _build_provider(name: str, settings: Settings) -> LLMProvider:
    """按名称构造 Provider,未知名称回退到 Mock。"""
    key = (name or "mock").strip().lower()
    if key == "openai":
        return OpenAICompatProvider(settings)
    if key == "zai":
        return ZAICompatProvider(settings)
    if key == "anthropic":
        return AnthropicProvider(settings)
    if key == "litellm":
        # 局部 import:litellm 较重,仅在选用时加载
        from app.llm.providers import LiteLLMProvider

        return LiteLLMProvider(settings)
    if key != "mock":
        logger.warning("未知 LLM provider %r,回退到 mock", name)
    return MockLLMProvider()


def _backoff_delay(attempt: int, base: float, cap: float) -> float:
    """计算第 attempt 次重试的指数退避时长(秒)。"""
    return min(cap, base * (2**attempt))


class LLMRouter:
    """根据意图与配置选择 Provider,并封装超时/重试/降级。"""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        base_delay_s: float = _DEFAULT_BASE_DELAY_S,
        max_delay_s: float = _DEFAULT_MAX_DELAY_S,
    ) -> None:
        """初始化路由器,记录主 Provider 名称与重试参数。"""
        self._settings = settings or get_settings()
        self._max_retries = max_retries
        self._base_delay_s = base_delay_s
        self._max_delay_s = max_delay_s
        self._fallback = MockLLMProvider()

    def select(
        self, intent: IntentType | None = None, context: Any = None
    ) -> LLMProvider:
        """按配置选择 Provider。

        当前策略:统一依据 settings.llm_provider 选择;intent/context 预留
        给后续按意图做差异化路由(例如 CHITCHAT 用更轻量模型)。
        """
        return _build_provider(self._settings.llm_provider, self._settings)

    async def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        intent: IntentType | None = None,
        **kwargs: Any,
    ) -> str:
        """健壮的一次性补全:超时 + 指数退避重试,最终降级到 Mock。"""
        provider = self.select(intent, kwargs.get("context"))
        timeout = self._settings.request_timeout_s
        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                return await asyncio.wait_for(
                    provider.complete(messages, **kwargs), timeout=timeout
                )
            except Exception as exc:  # noqa: BLE001 - 统一降级处理
                last_exc = exc
                await self._sleep_before_retry(provider.name, attempt, exc)
        return await self._fallback_complete(messages, last_exc, **kwargs)

    async def stream(
        self,
        messages: list[dict[str, Any]],
        *,
        intent: IntentType | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """健壮的流式补全。

        在产出首个 token 前若失败则重试;若所有重试均失败,降级到 Mock 流式。
        注意:一旦已向下游 yield 过 token,不再重试(避免重复输出),
        而是结束本次流。
        """
        provider = self.select(intent, kwargs.get("context"))
        for attempt in range(self._max_retries + 1):
            produced = False
            try:
                async for token in self._stream_with_timeout(
                    provider, messages, **kwargs
                ):
                    produced = True
                    yield token
                return
            except Exception as exc:  # noqa: BLE001 - 统一降级处理
                if produced:
                    logger.error(
                        "provider %s 流中途失败,已产出部分内容,停止重试: %s",
                        provider.name,
                        exc,
                    )
                    return
                await self._sleep_before_retry(provider.name, attempt, exc)
        async for token in self._fallback.stream(messages, **kwargs):
            yield token

    async def _stream_with_timeout(
        self, provider: LLMProvider, messages: list[dict[str, Any]], **kwargs: Any
    ) -> AsyncIterator[str]:
        """对底层 stream 的每个 token 施加单步超时。"""
        timeout = self._settings.request_timeout_s
        iterator = provider.stream(messages, **kwargs).__aiter__()
        while True:
            try:
                token = await asyncio.wait_for(
                    iterator.__anext__(), timeout=timeout
                )
            except StopAsyncIteration:
                return
            yield token

    async def _sleep_before_retry(
        self, provider_name: str, attempt: int, exc: Exception
    ) -> None:
        """记录失败并在重试前退避等待。"""
        if attempt < self._max_retries:
            delay = _backoff_delay(
                attempt, self._base_delay_s, self._max_delay_s
            )
            logger.warning(
                "provider %s 调用失败(第 %d 次),%.2fs 后重试: %s",
                provider_name,
                attempt + 1,
                delay,
                exc,
            )
            await asyncio.sleep(delay)
        else:
            logger.error(
                "provider %s 重试耗尽,准备降级到 mock: %s", provider_name, exc
            )

    async def _fallback_complete(
        self,
        messages: list[dict[str, Any]],
        exc: Exception | None,
        **kwargs: Any,
    ) -> str:
        """降级到 Mock 的一次性补全。"""
        logger.error("LLM 调用失败,使用 mock 兜底回答: %s", exc)
        return await self._fallback.complete(messages, **kwargs)
