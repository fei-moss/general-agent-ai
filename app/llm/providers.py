"""LLM Provider 具体实现。

包含三个实现,均满足 app.core.interfaces.LLMProvider 协议:

- MockLLMProvider: 零外部依赖,基于 RAG 上下文与问题做模板化中文回答,
  流式逐 token(逐字符片段)产出。保证整个系统在无任何 API key 时可端到端跑通。
- OpenAICompatProvider: 走 OpenAI 兼容 /chat/completions 端点,httpx 流式 SSE 解析。
- AnthropicProvider: 走 Anthropic /v1/messages 端点,httpx 流式 SSE 解析。

所有外部调用都有超时控制;解析失败时记录日志并安全终止流。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, AsyncIterator

import httpx

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.secrets import build_secret_provider

logger = get_logger(__name__)

# Mock 流式产出的最小片段长度(按字符切分)
_MOCK_CHUNK_SIZE = 2
# OpenAI/Anthropic SSE 流的结束标记
_SSE_DONE = "[DONE]"


@dataclass(frozen=True)
class ProviderErrorInfo:
    status_code: int
    retry_after_ms: int | None = None
    reason: str = "provider_error"


def map_provider_error(exc: Exception) -> ProviderErrorInfo | None:
    """Map provider/SDK exceptions to sanitized retry metadata when possible."""
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    if status_code is None:
        status_code = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    if status_code is None and isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        response = exc.response
    try:
        status_code = int(status_code)
    except (TypeError, ValueError):
        return None
    if status_code < 429 and status_code < 500:
        return None
    retry_after_ms = _extract_retry_after_ms(response, exc)
    reason = "provider_rate_limited" if status_code == 429 else "provider_transient"
    return ProviderErrorInfo(
        status_code=status_code,
        retry_after_ms=retry_after_ms,
        reason=reason,
    )


def _extract_retry_after_ms(response: Any, exc: Exception) -> int | None:
    value = None
    headers = getattr(response, "headers", None)
    if headers is not None:
        value = headers.get("retry-after") or headers.get("Retry-After")
    value = value or getattr(exc, "retry_after", None)
    if value is None:
        return None
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return None
    return max(0, int(seconds * 1000))


def _extract_question(messages: list[dict[str, Any]]) -> str:
    """从消息列表中取最后一条 user 消息内容作为问题。"""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            return str(msg.get("content", "")).strip()
    return ""


def _extract_context(messages: list[dict[str, Any]], **kwargs: Any) -> str:
    """提取 RAG 上下文。

    优先取 kwargs["context"];否则从 system 消息内容拼接,作为模板回答的依据。
    """
    ctx = kwargs.get("context")
    if isinstance(ctx, str) and ctx.strip():
        return ctx.strip()
    if isinstance(ctx, (list, tuple)):
        return "\n".join(str(c) for c in ctx if c).strip()
    system_parts = [
        str(m.get("content", ""))
        for m in messages
        if m.get("role") == "system"
    ]
    return "\n".join(p for p in system_parts if p).strip()


def _compose_mock_answer(messages: list[dict[str, Any]], **kwargs: Any) -> str:
    """根据问题与 RAG 上下文生成模板化中文回答。"""
    question = _extract_question(messages)
    context = _extract_context(messages, **kwargs)
    if not question:
        return "你好,我是内置的离线助手,请告诉我你的问题。"
    if context:
        return (
            f"根据已检索到的资料,针对「{question}」的回答如下:\n"
            f"{context}\n"
            "(以上内容由内置 Mock 模型基于检索上下文生成,供演示使用。)"
        )
    return (
        f"你问的是「{question}」。当前没有检索到相关资料,"
        "这是内置 Mock 模型的离线模板回答,用于在无外部模型时演示完整链路。"
    )


class MockLLMProvider:
    """离线确定性 Provider:逐 token echo + 基于上下文的模板回答。"""

    @property
    def name(self) -> str:
        """Provider 名称。"""
        return "mock"

    async def stream(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> AsyncIterator[str]:
        """将模板回答按固定片段长度逐块产出,模拟流式生成。"""
        answer = _compose_mock_answer(messages, **kwargs)
        for i in range(0, len(answer), _MOCK_CHUNK_SIZE):
            yield answer[i : i + _MOCK_CHUNK_SIZE]

    async def complete(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> str:
        """一次性返回完整模板回答。"""
        return _compose_mock_answer(messages, **kwargs)


def _strip_provider_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    """剔除仅供 Mock 使用、真实 API 不识别的自定义参数(如 context)。"""
    return {k: v for k, v in kwargs.items() if k != "context"}


class OpenAICompatProvider:
    """OpenAI 兼容 Provider(可对接 OpenAI / vLLM / 任意兼容端点)。"""

    def __init__(self, settings: Settings | None = None) -> None:
        """从配置读取 base_url / api_key / model 与超时。"""
        self._settings = settings or get_settings()
        self._secret_provider = build_secret_provider(self._settings)
        self._timeout = self._settings.request_timeout_s

    @property
    def name(self) -> str:
        """Provider 名称。"""
        return "openai"

    def _payload(
        self, messages: list[dict[str, Any]], stream: bool, **kwargs: Any
    ) -> dict[str, Any]:
        """构造 /chat/completions 请求体。"""
        body: dict[str, Any] = {
            "model": kwargs.get("model", self._settings.openai_model),
            "messages": messages,
            "stream": stream,
        }
        extra = _strip_provider_kwargs(dict(kwargs))
        extra.pop("model", None)
        body.update(extra)
        return body

    def _headers(self) -> dict[str, str]:
        """构造带鉴权的请求头。缺少 key 时抛出明确错误。"""
        api_key = self._secret_provider.get_secret("openai_api_key")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY 未配置,无法调用 OpenAI 兼容端点")
        return {
            "Authorization": f"Bearer {api_key.reveal()}",
            "Content-Type": "application/json",
        }

    async def stream(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> AsyncIterator[str]:
        """流式调用并解析 SSE,逐 token 产出 delta.content。"""
        url = f"{self._settings.openai_base_url.rstrip('/')}/chat/completions"
        payload = self._payload(messages, stream=True, **kwargs)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            async with client.stream(
                "POST", url, headers=self._headers(), json=payload
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    token = _parse_openai_sse_line(line)
                    if token is None:
                        continue
                    if token == _SSE_DONE:
                        break
                    if token:
                        yield token

    async def complete(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> str:
        """一次性调用,返回首个 choice 的文本。"""
        url = f"{self._settings.openai_base_url.rstrip('/')}/chat/completions"
        payload = self._payload(messages, stream=False, **kwargs)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, headers=self._headers(), json=payload)
            resp.raise_for_status()
            data = resp.json()
        return _parse_openai_completion(data)


def _parse_openai_sse_line(line: str) -> str | None:
    """解析单行 OpenAI SSE。

    返回:None 表示忽略该行;`_SSE_DONE` 表示流结束;否则返回 delta 文本片段。
    """
    line = line.strip()
    if not line or not line.startswith("data:"):
        return None
    data = line[len("data:") :].strip()
    if data == _SSE_DONE:
        return _SSE_DONE
    try:
        obj = json.loads(data)
        delta = obj["choices"][0].get("delta", {})
        return delta.get("content") or ""
    except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
        logger.warning("OpenAI SSE 解析失败,已跳过该行: %s", exc)
        return None


def _parse_openai_completion(data: dict[str, Any]) -> str:
    """从非流式响应中提取文本,解析失败抛出明确错误。"""
    try:
        return str(data["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"OpenAI 响应结构异常: {exc}") from exc


class AnthropicProvider:
    """Anthropic Messages Provider(/v1/messages,流式 SSE)。"""

    _API_VERSION = "2023-06-01"

    def __init__(self, settings: Settings | None = None) -> None:
        """从配置读取 api_key / model 与超时。"""
        self._settings = settings or get_settings()
        self._secret_provider = build_secret_provider(self._settings)
        self._timeout = self._settings.request_timeout_s
        self._base_url = "https://api.anthropic.com/v1"

    @property
    def name(self) -> str:
        """Provider 名称。"""
        return "anthropic"

    def _headers(self) -> dict[str, str]:
        """构造带鉴权的请求头。缺少 key 时抛出明确错误。"""
        api_key = self._secret_provider.get_secret("anthropic_api_key")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY 未配置,无法调用 Anthropic 端点")
        return {
            "x-api-key": api_key.reveal(),
            "anthropic-version": self._API_VERSION,
            "Content-Type": "application/json",
        }

    def _payload(
        self, messages: list[dict[str, Any]], stream: bool, **kwargs: Any
    ) -> dict[str, Any]:
        """构造 /v1/messages 请求体,拆分 system 与对话消息。"""
        system, convo = _split_anthropic_messages(messages)
        body: dict[str, Any] = {
            "model": kwargs.get("model", self._settings.anthropic_model),
            "messages": convo,
            "max_tokens": kwargs.get("max_tokens", 1024),
            "stream": stream,
        }
        if system:
            body["system"] = system
        return body

    async def stream(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> AsyncIterator[str]:
        """流式调用并解析 SSE,逐 token 产出文本增量。"""
        url = f"{self._base_url}/messages"
        payload = self._payload(messages, stream=True, **kwargs)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            async with client.stream(
                "POST", url, headers=self._headers(), json=payload
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    token = _parse_anthropic_sse_line(line)
                    if token:
                        yield token

    async def complete(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> str:
        """一次性调用,拼接所有 text block。"""
        url = f"{self._base_url}/messages"
        payload = self._payload(messages, stream=False, **kwargs)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, headers=self._headers(), json=payload)
            resp.raise_for_status()
            data = resp.json()
        return _parse_anthropic_completion(data)


def _split_anthropic_messages(
    messages: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    """将 OpenAI 风格消息拆为 (system 文本, user/assistant 对话列表)。"""
    system_parts: list[str] = []
    convo: list[dict[str, Any]] = []
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content", "")
        if role == "system":
            system_parts.append(str(content))
        elif role in ("user", "assistant"):
            convo.append({"role": role, "content": content})
    return "\n".join(p for p in system_parts if p), convo


def _parse_anthropic_sse_line(line: str) -> str | None:
    """解析单行 Anthropic SSE,仅提取 content_block_delta 的 text。"""
    line = line.strip()
    if not line or not line.startswith("data:"):
        return None
    data = line[len("data:") :].strip()
    try:
        obj = json.loads(data)
        if obj.get("type") == "content_block_delta":
            return obj.get("delta", {}).get("text") or ""
        return None
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.warning("Anthropic SSE 解析失败,已跳过该行: %s", exc)
        return None


def _parse_anthropic_completion(data: dict[str, Any]) -> str:
    """从非流式响应拼接所有 text block,解析失败抛出明确错误。"""
    try:
        blocks = data["content"]
        return "".join(
            b.get("text", "") for b in blocks if b.get("type") == "text"
        )
    except (KeyError, TypeError) as exc:
        raise RuntimeError(f"Anthropic 响应结构异常: {exc}") from exc


def _sync_provider_keys_to_env(settings: Settings) -> None:
    """把 Settings 中配置的各厂商 key 注入进程环境变量,供 litellm 读取。

    仅在对应环境变量尚未设置时填充,不覆盖外部已注入的值,避免副作用扩散。
    """
    import os

    secret_provider = build_secret_provider(settings)
    mapping = {
        "OPENAI_API_KEY": secret_provider.get_secret("openai_api_key"),
        "ANTHROPIC_API_KEY": secret_provider.get_secret("anthropic_api_key"),
        "GEMINI_API_KEY": secret_provider.get_secret("gemini_api_key"),
        "DASHSCOPE_API_KEY": secret_provider.get_secret("dashscope_api_key"),
    }
    for env_name, secret in mapping.items():
        if secret and not os.environ.get(env_name):
            os.environ[env_name] = secret.reveal()


def _extract_litellm_delta(chunk: Any) -> str:
    """从 litellm 流式 chunk 中安全提取增量文本(兼容对象/字典两种形态)。"""
    try:
        choices = getattr(chunk, "choices", None)
        if choices is None and isinstance(chunk, dict):
            choices = chunk.get("choices")
        first = choices[0]
        delta = getattr(first, "delta", None)
        if delta is None and isinstance(first, dict):
            delta = first.get("delta", {})
        content = (
            delta.get("content")
            if isinstance(delta, dict)
            else getattr(delta, "content", None)
        )
        return content or ""
    except (AttributeError, KeyError, IndexError, TypeError):
        return ""


def _extract_litellm_content(resp: Any) -> str:
    """从 litellm 非流式响应中提取完整文本,结构异常时抛出明确错误。"""
    try:
        choices = getattr(resp, "choices", None)
        if choices is None and isinstance(resp, dict):
            choices = resp["choices"]
        first = choices[0]
        message = getattr(first, "message", None)
        if message is None and isinstance(first, dict):
            message = first["message"]
        content = (
            message.get("content")
            if isinstance(message, dict)
            else getattr(message, "content", None)
        )
        return str(content or "")
    except (AttributeError, KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"LiteLLM 响应结构异常: {exc}") from exc


class LiteLLMProvider:
    """通过 LiteLLM 统一网关调用任意厂商模型(OpenAI / Claude / Qwen / Gemini ...)。

    model 用 litellm 的 provider 前缀写法:openai/gpt-4o、
    anthropic/claude-sonnet-4-6、gemini/gemini-2.5-flash、dashscope/qwen-plus。
    各厂商 API key 通过标准环境变量提供(OPENAI_API_KEY / ANTHROPIC_API_KEY /
    GEMINI_API_KEY / DASHSCOPE_API_KEY),由 litellm 自动读取;主模型失败时按
    settings.litellm_fallback_list 跨厂商降级(由 litellm 内部完成)。
    """

    def __init__(self, settings: Settings | None = None) -> None:
        """读取主模型 / fallback 链 / 超时,并把已配置的 key 注入环境。"""
        self._settings = settings or get_settings()
        self._model = self._settings.litellm_model
        self._fallbacks = self._settings.litellm_fallback_list
        self._timeout = self._settings.request_timeout_s
        _sync_provider_keys_to_env(self._settings)

    @property
    def name(self) -> str:
        """Provider 名称(含当前主模型,便于日志区分)。"""
        return f"litellm:{self._model}"

    def _call_kwargs(self, **kwargs: Any) -> dict[str, Any]:
        """构造 litellm.acompletion 的调用参数(含 fallback 与超时)。"""
        extra = _strip_provider_kwargs(dict(kwargs))
        extra.pop("model", None)
        params: dict[str, Any] = {
            "model": kwargs.get("model", self._model),
            "timeout": self._timeout,
        }
        if self._fallbacks:
            params["fallbacks"] = self._fallbacks
        params.update(extra)  # 允许覆盖 temperature/max_tokens 等
        return params

    async def stream(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> AsyncIterator[str]:
        """流式调用,逐 token 产出增量文本。"""
        import litellm

        params = self._call_kwargs(**kwargs)
        response = await litellm.acompletion(
            messages=messages, stream=True, **params
        )
        async for chunk in response:
            token = _extract_litellm_delta(chunk)
            if token:
                yield token

    async def complete(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> str:
        """一次性调用,返回完整文本。"""
        import litellm

        params = self._call_kwargs(**kwargs)
        response = await litellm.acompletion(
            messages=messages, stream=False, **params
        )
        return _extract_litellm_content(response)
