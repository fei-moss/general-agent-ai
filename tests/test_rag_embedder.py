from __future__ import annotations

import json

import httpx
import pytest

from app.core.config import Settings


def test_default_embedder_is_hash_without_secret():
    from app.rag.embedder import HashEmbedder, get_embedder

    embedder = get_embedder(Settings(_env_file=None))

    assert isinstance(embedder, HashEmbedder)


def test_explicit_openai_embedder_missing_secret_fails_fast():
    from app.rag.embedder import get_embedder

    with pytest.raises(ValueError, match="embedding_api_key"):
        get_embedder(Settings(_env_file=None, embedding_provider="openai"))


def test_explicit_gemini_embedder_missing_secret_fails_fast():
    from app.rag.embedder import get_embedder

    with pytest.raises(ValueError, match="gemini_api_key"):
        get_embedder(Settings(_env_file=None, embedding_provider="gemini"))


def test_get_embedder_builds_gemini_from_gemini_api_key():
    from app.rag.embedder import GeminiEmbedder, get_embedder

    embedder = get_embedder(
        Settings(
            _env_file=None,
            embedding_provider="gemini",
            embedding_model="gemini-embedding-2",
            gemini_api_key="local-test-key",
            embedding_dim=3,
        )
    )

    assert isinstance(embedder, GeminiEmbedder)
    assert embedder.name == "gemini"
    assert embedder.dim == 3


async def test_gemini_embedder_uses_batch_endpoint_and_parses_vectors(monkeypatch):
    from app.rag.embedder import GeminiEmbedder

    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json={
                "embeddings": [
                    {"values": [1.0, 0.0, 0.0]},
                    {"values": [0.0, 1.0, 0.0]},
                ],
                "usageMetadata": {"promptTokenCount": 7},
            },
        )

    transport = httpx.MockTransport(handler)
    original_async_client = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        kwargs["transport"] = transport
        return original_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)

    embedder = GeminiEmbedder(
        Settings(
            _env_file=None,
            embedding_provider="gemini",
            embedding_model="models/gemini-embedding-2",
            embedding_api_key="gem-test-key",
            embedding_base_url="https://generativelanguage.googleapis.com/v1beta",
            embedding_dim=3,
        )
    )

    vectors = await embedder.embed(["alpha", "beta"])

    assert vectors == [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
    assert len(captured) == 1
    request = captured[0]
    assert str(request.url) == (
        "https://generativelanguage.googleapis.com/v1beta/"
        "models/gemini-embedding-2:batchEmbedContents"
    )
    assert request.headers["x-goog-api-key"] == "gem-test-key"
    payload = json.loads(request.content)
    assert payload == {
        "requests": [
            {
                "model": "models/gemini-embedding-2",
                "content": {"parts": [{"text": "alpha"}]},
                "output_dimensionality": 3,
            },
            {
                "model": "models/gemini-embedding-2",
                "content": {"parts": [{"text": "beta"}]},
                "output_dimensionality": 3,
            },
        ]
    }


async def test_gemini_embedder_uses_gemini_defaults_when_model_base_url_omitted(
    monkeypatch,
):
    from app.rag.embedder import GeminiEmbedder

    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"embeddings": [{"values": [1.0, 0.0]}]})

    transport = httpx.MockTransport(handler)
    original_async_client = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        kwargs["transport"] = transport
        return original_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)

    embedder = GeminiEmbedder(
        Settings(
            _env_file=None,
            embedding_provider="gemini",
            gemini_api_key="gem-test-key",
            embedding_dim=2,
        )
    )

    vectors = await embedder.embed(["alpha"])

    assert vectors == [[1.0, 0.0]]
    assert str(captured[0].url) == (
        "https://generativelanguage.googleapis.com/v1beta/"
        "models/gemini-embedding-2:batchEmbedContents"
    )


async def test_gemini_embedder_rejects_wrong_response_count(monkeypatch):
    from app.rag.embedder import GeminiEmbedder

    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"embeddings": [{"values": [1.0]}]})
    )
    original_async_client = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        kwargs["transport"] = transport
        return original_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)

    embedder = GeminiEmbedder(
        Settings(
            _env_file=None,
            embedding_provider="gemini",
            embedding_model="gemini-embedding-2",
            embedding_api_key="gem-test-key",
            embedding_dim=1,
        )
    )

    with pytest.raises(ValueError, match="embedding_count_mismatch"):
        await embedder.embed(["alpha", "beta"])
