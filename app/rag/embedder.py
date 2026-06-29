"""文本向量化实现。

提供两种 Embedder:
- HashEmbedder: 零外部依赖、确定性的 hashing-trick 向量化(默认),
  保证无任何 API key 也能端到端跑通。
- OpenAIEmbedder: 可选,经 httpx 调用 OpenAI 兼容 /embeddings 接口。
- GeminiEmbedder: 可选,经 Gemini API batchEmbedContents 生成语义向量。

工厂 get_embedder() 按 Settings.embedding_provider 选择。默认 hash 零依赖;
显式真实 provider 缺少 secret 时失败,避免生产静默退回 hash。
"""

from __future__ import annotations

import hashlib
import logging
import re

import numpy as np

from app.core.config import Settings, get_settings
from app.core.interfaces import Embedder
from app.core.logging import get_logger, log_with_fields
from app.core.secrets import build_secret_provider

logger = get_logger(__name__)

# 分词:抓取连续的字母数字,或单个非空白字符(覆盖中文按字切)
_TOKEN_RE = re.compile(r"[A-Za-z0-9]+|[^\sA-Za-z0-9]")
# OpenAI 默认 embedding 模型
_OPENAI_EMBED_MODEL = "text-embedding-3-small"
_OPENAI_BASE_URL = "https://api.openai.com/v1"
_GEMINI_EMBED_MODEL = "gemini-embedding-2"
_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
_EPS = 1e-12


def _tokenize(text: str) -> list[str]:
    """轻量分词:小写化后抽取词/单字符 token。"""
    return _TOKEN_RE.findall(text.lower())


def _secret_value(settings: Settings, *names: str) -> str:
    """按优先级读取 secret,支持 Settings 字段和 *_file 注入。"""
    provider = build_secret_provider(settings)
    for name in names:
        secret = provider.get_secret(name)
        if secret:
            return secret.reveal()
    return ""


def _gemini_model_resource(model: str | None) -> str:
    """规范化 Gemini model resource,用于请求体与 URL。"""
    value = (model or _GEMINI_EMBED_MODEL).strip()
    if value.startswith("models/"):
        return value
    return f"models/{value}"


def _provider_model(settings: Settings, default: str) -> str:
    """返回真实 provider 的模型名,忽略 hash 默认占位值。"""
    model = (settings.embedding_model or "").strip()
    if not model or model == "hash":
        return default
    return model


class HashEmbedder:
    """基于 hashing trick 的确定性向量化器。

    对每个 token 用稳定哈希映射到维度桶并带符号累加,最后 L2 归一化。
    不依赖任何外部服务或模型,相同输入恒定产出相同向量。
    """

    def __init__(self, dim: int = 256) -> None:
        """初始化。

        参数:
            dim: 输出向量维度,必须为正整数。
        """
        if dim <= 0:
            raise ValueError("embedding dim 必须为正整数")
        self._dim = dim

    @property
    def name(self) -> str:
        """实现名称。"""
        return "hash"

    @property
    def dim(self) -> int:
        """输出向量维度。"""
        return self._dim

    def _embed_one(self, text: str) -> list[float]:
        """将单条文本编码为归一化向量。"""
        vec = np.zeros(self._dim, dtype=np.float64)
        for token in _tokenize(text):
            digest = hashlib.md5(token.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], "little") % self._dim
            sign = 1.0 if digest[4] & 1 else -1.0
            vec[bucket] += sign
        norm = float(np.linalg.norm(vec))
        if norm < _EPS:
            return vec.tolist()  # 全零(空文本),保持零向量
        return (vec / norm).tolist()

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """批量向量化,顺序与输入一致。"""
        return [self._embed_one(t or "") for t in texts]


class OpenAIEmbedder:
    """经 OpenAI 兼容接口的向量化器(可选)。

    使用 httpx 异步调用 {base_url}/embeddings,带超时。失败由调用方
    (工厂)负责降级。维度以配置声明值为准。
    """

    def __init__(self, settings: Settings) -> None:
        """初始化,记录配置(不在构造期发起网络请求)。"""
        api_key = _secret_value(settings, "embedding_api_key", "openai_api_key")
        if not api_key:
            raise ValueError("OpenAIEmbedder 需要 embedding_api_key")
        self._base_url = (
            settings.embedding_base_url or settings.openai_base_url
        ).rstrip("/")
        self._api_key = api_key
        self._model = _provider_model(settings, _OPENAI_EMBED_MODEL)
        self._timeout = settings.embedding_timeout_s
        self._dim = settings.embedding_dim

    @property
    def name(self) -> str:
        """实现名称。"""
        return "openai"

    @property
    def dim(self) -> int:
        """输出向量维度(配置声明值)。"""
        return self._dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """调用远端接口批量向量化。

        异常:
            httpx 相关异常或 KeyError 在请求失败时向上抛出,
            由工厂或调用方决定降级策略。
        """
        import httpx  # 延迟导入,避免无网络场景的导入成本

        payload = {"model": self._model, "input": [t or "" for t in texts]}
        headers = {"Authorization": f"Bearer {self._api_key}"}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._base_url}/embeddings", json=payload, headers=headers
            )
            resp.raise_for_status()
            data = resp.json()
        items = sorted(data["data"], key=lambda d: d["index"])
        return [item["embedding"] for item in items]


class GeminiEmbedder:
    """经 Gemini API 的向量化器。

    使用 batchEmbedContents,确保批量输入返回一组与输入顺序一致的
    embeddings。Gemini key 通过 x-goog-api-key 传递,不进入日志。
    """

    def __init__(self, settings: Settings) -> None:
        """初始化,记录配置(不在构造期发起网络请求)。"""
        api_key = _secret_value(settings, "embedding_api_key", "gemini_api_key")
        if not api_key:
            raise ValueError("GeminiEmbedder 需要 embedding_api_key 或 gemini_api_key")
        self._api_key = api_key
        base_url = (settings.embedding_base_url or "").strip().rstrip("/")
        if not base_url or base_url == _OPENAI_BASE_URL:
            base_url = _GEMINI_BASE_URL
        self._base_url = base_url
        self._model_resource = _gemini_model_resource(
            _provider_model(settings, _GEMINI_EMBED_MODEL)
        )
        self._timeout = settings.embedding_timeout_s
        self._dim = settings.embedding_dim

    @property
    def name(self) -> str:
        """实现名称。"""
        return "gemini"

    @property
    def dim(self) -> int:
        """输出向量维度(配置声明值)。"""
        return self._dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """调用 Gemini batchEmbedContents 批量向量化。"""
        if not texts:
            return []

        import httpx  # 延迟导入,避免无网络场景的导入成本

        payload = {
            "requests": [
                {
                    "model": self._model_resource,
                    "content": {"parts": [{"text": text or ""}]},
                    "output_dimensionality": self._dim,
                }
                for text in texts
            ]
        }
        headers = {"x-goog-api-key": self._api_key}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._base_url}/{self._model_resource}:batchEmbedContents",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

        embeddings = data["embeddings"]
        if len(embeddings) != len(texts):
            raise ValueError("embedding_count_mismatch")
        vectors = [[float(v) for v in item["values"]] for item in embeddings]
        for vector in vectors:
            if len(vector) != self._dim:
                raise ValueError("embedding_dimension_mismatch")
        return vectors


def get_embedder(settings: Settings | None = None) -> Embedder:
    """工厂:按配置返回 Embedder 实例。

    默认 hash 保持零依赖。显式选择真实 provider 时缺 secret 会失败,
    避免生产把语义检索静默变成 hash 检索。
    """
    settings = settings or get_settings()
    provider = (settings.embedding_provider or "hash").strip().lower()
    if provider == "openai":
        try:
            return OpenAIEmbedder(settings)
        except Exception as exc:  # noqa: BLE001 — 降级保证可用性
            if not _secret_value(settings, "embedding_api_key", "openai_api_key"):
                raise
            log_with_fields(
                logger,
                logging.WARNING,
                "OpenAIEmbedder 初始化失败,降级到 HashEmbedder",
                error=str(exc),
            )
    if provider == "gemini":
        try:
            return GeminiEmbedder(settings)
        except Exception as exc:  # noqa: BLE001 — 降级保证可用性
            if not _secret_value(settings, "embedding_api_key", "gemini_api_key"):
                raise
            log_with_fields(
                logger,
                logging.WARNING,
                "GeminiEmbedder 初始化失败,降级到 HashEmbedder",
                error=str(exc),
            )
    return HashEmbedder(dim=settings.embedding_dim)
