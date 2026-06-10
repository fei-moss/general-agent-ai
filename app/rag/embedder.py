"""文本向量化实现。

提供两种 Embedder:
- HashEmbedder: 零外部依赖、确定性的 hashing-trick 向量化(默认),
  保证无任何 API key 也能端到端跑通。
- OpenAIEmbedder: 可选,经 httpx 调用 OpenAI 兼容 /embeddings 接口。

工厂 get_embedder() 按 Settings.llm_provider 选择,失败降级到 HashEmbedder。
"""

from __future__ import annotations

import hashlib
import logging
import re

import numpy as np

from app.core.config import Settings, get_settings
from app.core.interfaces import Embedder
from app.core.logging import get_logger, log_with_fields

logger = get_logger(__name__)

# 分词:抓取连续的字母数字,或单个非空白字符(覆盖中文按字切)
_TOKEN_RE = re.compile(r"[A-Za-z0-9]+|[^\sA-Za-z0-9]")
# OpenAI 默认 embedding 模型
_OPENAI_EMBED_MODEL = "text-embedding-3-small"
_EPS = 1e-12


def _tokenize(text: str) -> list[str]:
    """轻量分词:小写化后抽取词/单字符 token。"""
    return _TOKEN_RE.findall(text.lower())


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
        if not settings.openai_api_key:
            raise ValueError("OpenAIEmbedder 需要 openai_api_key")
        self._base_url = settings.openai_base_url.rstrip("/")
        self._api_key = settings.openai_api_key
        self._model = _OPENAI_EMBED_MODEL
        self._timeout = settings.request_timeout_s
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


def get_embedder(settings: Settings | None = None) -> Embedder:
    """工厂:按配置返回 Embedder 实例。

    provider 为 openai 且具备 api_key 时尝试 OpenAIEmbedder,
    构造失败则记录并降级到 HashEmbedder;其余情况默认 HashEmbedder。
    """
    settings = settings or get_settings()
    if settings.llm_provider == "openai" and settings.openai_api_key:
        try:
            return OpenAIEmbedder(settings)
        except Exception as exc:  # noqa: BLE001 — 降级保证可用性
            log_with_fields(
                logger,
                logging.WARNING,
                "OpenAIEmbedder 初始化失败,降级到 HashEmbedder",
                error=str(exc),
            )
    return HashEmbedder(dim=settings.embedding_dim)
