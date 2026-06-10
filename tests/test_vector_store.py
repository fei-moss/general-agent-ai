"""InMemoryVectorStore 检索正确性测试。"""

from __future__ import annotations

import pytest

from app.rag.vector_store import InMemoryVectorStore, get_vector_store


async def test_search_returns_most_similar_doc_first():
    # Arrange
    store = InMemoryVectorStore()
    await store.add(
        [
            {"id": "a", "text": "向上", "vector": [1.0, 0.0]},
            {"id": "b", "text": "向右", "vector": [0.0, 1.0]},
            {"id": "c", "text": "对角", "vector": [1.0, 1.0]},
        ]
    )

    # Act
    results = await store.search([1.0, 0.0], top_k=3)

    # Assert
    assert results[0][0]["id"] == "a"
    assert results[0][1] == pytest.approx(1.0)


async def test_search_respects_top_k_limit():
    # Arrange
    store = InMemoryVectorStore()
    await store.add(
        [
            {"id": "a", "text": "x", "vector": [1.0, 0.0]},
            {"id": "b", "text": "y", "vector": [0.9, 0.1]},
            {"id": "c", "text": "z", "vector": [0.0, 1.0]},
        ]
    )

    # Act
    results = await store.search([1.0, 0.0], top_k=2)

    # Assert
    assert len(results) == 2
    assert [r[0]["id"] for r in results] == ["a", "b"]


async def test_search_returns_descending_scores():
    # Arrange
    store = InMemoryVectorStore()
    await store.add(
        [
            {"id": "near", "text": "n", "vector": [1.0, 0.0]},
            {"id": "mid", "text": "m", "vector": [0.7, 0.7]},
            {"id": "far", "text": "f", "vector": [-1.0, 0.0]},
        ]
    )

    # Act
    results = await store.search([1.0, 0.0], top_k=3)

    # Assert
    scores = [score for _, score in results]
    assert scores == sorted(scores, reverse=True)
    assert results[0][0]["id"] == "near"
    assert results[-1][0]["id"] == "far"


async def test_search_on_empty_store_returns_empty_list():
    # Arrange
    store = InMemoryVectorStore()

    # Act
    results = await store.search([1.0, 0.0], top_k=5)

    # Assert
    assert results == []


async def test_search_with_non_positive_top_k_returns_empty_list():
    # Arrange
    store = InMemoryVectorStore()
    await store.add([{"id": "a", "text": "x", "vector": [1.0, 0.0]}])

    # Act
    results = await store.search([1.0, 0.0], top_k=0)

    # Assert
    assert results == []


async def test_add_overwrites_doc_with_same_id():
    # Arrange
    store = InMemoryVectorStore()
    await store.add([{"id": "a", "text": "old", "vector": [1.0, 0.0]}])

    # Act
    await store.add([{"id": "a", "text": "new", "vector": [0.0, 1.0]}])

    # Assert
    assert store.size == 1
    results = await store.search([0.0, 1.0], top_k=1)
    assert results[0][0]["text"] == "new"


async def test_add_rejects_doc_missing_required_fields():
    # Arrange
    store = InMemoryVectorStore()

    # Act / Assert
    with pytest.raises(ValueError):
        await store.add([{"id": "a", "text": "no vector"}])


async def test_search_raises_on_dimension_mismatch():
    # Arrange
    store = InMemoryVectorStore()
    await store.add([{"id": "a", "text": "x", "vector": [1.0, 0.0, 0.0]}])

    # Act / Assert
    with pytest.raises(ValueError):
        await store.search([1.0, 0.0], top_k=1)


async def test_add_copies_doc_to_prevent_external_mutation():
    # Arrange
    store = InMemoryVectorStore()
    doc = {"id": "a", "text": "orig", "vector": [1.0, 0.0]}
    await store.add([doc])

    # Act
    doc["text"] = "mutated externally"

    # Assert
    results = await store.search([1.0, 0.0], top_k=1)
    assert results[0][0]["text"] == "orig"


def test_factory_returns_in_memory_store_by_default():
    # Arrange / Act
    store = get_vector_store()

    # Assert
    assert isinstance(store, InMemoryVectorStore)
