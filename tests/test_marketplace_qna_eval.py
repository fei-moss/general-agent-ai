from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import pytest


EVAL_DIR = Path(__file__).parent / "rag_eval"


def _normalize(value: str) -> str:
    return "".join(character.casefold() for character in value if character.isalnum())


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_marketplace_qna_sources_have_expected_shape():
    from tests.rag_eval.marketplace_qna_fixture_builder import build_fixture_bundle

    bundle = build_fixture_bundle()

    assert len(bundle.sources) == 18
    assert sum(source.language == "zh-CN" for source in bundle.sources) == 9
    assert sum(source.language == "en" for source in bundle.sources) == 9
    assert sum(len(source.questions) for source in bundle.sources) == 114
    assert {len(source.questions) for source in bundle.sources if source.order == 4} == {16}


def test_marketplace_qna_case_definitions_cover_every_question_with_semantic_paraphrases():
    from tests.rag_eval.marketplace_qna_fixture_builder import (
        build_fixture_bundle,
        load_case_definitions,
    )

    bundle = build_fixture_bundle()
    cases = load_case_definitions(bundle)
    source_questions = {
        question.id: question
        for source in bundle.sources
        for question in source.questions
    }

    assert len(cases) == 114
    assert Counter(case.language for case in cases.values()) == {"zh-CN": 57, "en": 57}
    assert set(cases) == set(source_questions)
    assert all(case.query.strip() for case in cases.values())
    assert all(
        _normalize(case.query) != _normalize(source_questions[case_id].question)
        for case_id, case in cases.items()
    )
    assert all(case.challenge_type for case in cases.values())
    assert all(case.required_facts for case in cases.values())
    assert all(case.review_reason for case in cases.values())
    assert sum(case.representative_chat for case in cases.values()) == 18
    assert Counter(
        case.document_id for case in cases.values() if case.representative_chat
    ) == {source.id: 1 for source in bundle.sources}


def test_marketplace_qna_generated_fixture_rows_are_complete_and_traceable():
    from tests.rag_eval.marketplace_qna_fixture_builder import build_fixture_rows

    rows = build_fixture_rows()

    assert len(rows.corpus) == 18
    assert len(rows.golden_queries) == 114
    assert len(rows.review_evidence) == 114
    assert len(rows.chat_cases) == 18
    assert {row["id"] for row in rows.corpus} == {
        row["relevant_doc_ids"][0] for row in rows.golden_queries
    }
    assert {row["id"] for row in rows.golden_queries} == {
        row["id"] for row in rows.review_evidence
    }
    assert all(row["max_rank"] == 5 and row["top_k"] == 5 for row in rows.golden_queries)
    assert all(row["source_evidence"] for row in rows.review_evidence)
    assert all(row["required_facts"] for row in rows.chat_cases)


def test_marketplace_qna_coverage_and_acceptance_contracts_match_fixtures():
    coverage = json.loads(
        (EVAL_DIR / "marketplace_qna_coverage_contract.json").read_text(encoding="utf-8")
    )
    acceptance = json.loads(
        (EVAL_DIR / "marketplace_qna_acceptance_evidence_contract.json").read_text(
            encoding="utf-8"
        )
    )
    golden = _read_jsonl(EVAL_DIR / "marketplace_qna_golden_queries.jsonl")
    chat = _read_jsonl(EVAL_DIR / "marketplace_qna_chat_cases.jsonl")

    assert coverage["contract_id"] == "SPEC-RAG-EVAL-002-MARKETPLACE-QNA-COVERAGE"
    assert len(coverage["topic_groups"]) == 18
    assert {group["language"] for group in coverage["topic_groups"]} == {"zh-CN", "en"}
    assert {query_id for group in coverage["topic_groups"] for query_id in group["query_ids"]} == {
        row["id"] for row in golden
    }
    assert acceptance["thresholds"] == {
        "source_documents": 18,
        "golden_queries": 114,
        "chat_cases": 18,
        "promptfoo_required_passes": 114,
        "live_required_passes": 114,
        "minimum_top1_rate": 0.8,
        "maximum_degraded_cases": 0,
        "maximum_failed_ingestion_jobs": 0,
    }
    assert len(golden) == acceptance["thresholds"]["golden_queries"]
    assert len(chat) == acceptance["thresholds"]["chat_cases"]


def test_marketplace_qna_seed_manifest_hashes_every_reviewed_fixture():
    manifest = json.loads(
        (EVAL_DIR / "marketplace_qna_rag_seed_manifest.json").read_text(encoding="utf-8")
    )

    assert manifest["spec_id"] == "SPEC-RAG-EVAL-002"
    assert manifest["embedding_target"] == {
        "provider": "gemini",
        "model": "gemini-embedding-2",
        "dimension": 256,
        "requires_allowed_network": True,
    }
    assert {entry["role"] for entry in manifest["source_files"]} == {
        "corpus",
        "golden_queries",
        "review_evidence",
        "chat_cases",
        "coverage_contract",
        "acceptance_contract",
    }
    for entry in manifest["source_files"]:
        path = Path(__file__).parents[1] / entry["path"]
        assert path.exists()
        assert entry["sha256"] == _sha256(path)
        if entry["row_count"] is not None:
            assert entry["row_count"] == len(_read_jsonl(path))


def test_marketplace_qna_import_payloads_match_rag_document_schema():
    from app.core.schemas import RAGDocumentCreate
    from tests.rag_eval.marketplace_qna_import_payloads import build_document_payloads

    payloads = build_document_payloads(knowledge_base_id="kb_marketplace_qna")

    assert len(payloads) == 18
    assert {payload["metadata"]["doc_id"] for payload in payloads} == {
        row["id"] for row in _read_jsonl(EVAL_DIR / "marketplace_qna_corpus.jsonl")
    }
    for payload in payloads:
        parsed = RAGDocumentCreate(**payload)
        assert parsed.knowledge_base_id == "kb_marketplace_qna"
        assert parsed.source_type == "api"
        assert parsed.mime_type == "text/markdown"
        assert parsed.source_uri.startswith("marketplace-qna://")
        assert parsed.metadata["sha256"]
        assert parsed.metadata["source_set"] == "marketplace-qna-bilingual-2026-07-16"


def test_marketplace_qna_promptfoo_adapter_and_config_use_production_retrieval_settings():
    from tests.rag_eval.marketplace_qna_test_cases import generate_tests

    cases = generate_tests()
    config = (EVAL_DIR / "marketplace_qna_promptfooconfig.yaml").read_text(encoding="utf-8")

    assert len(cases) == 114
    assert all(case["vars"]["max_rank"] == 5 for case in cases)
    assert all(case["vars"]["top_k"] == 5 for case in cases)
    assert Counter(case["vars"]["language"] for case in cases) == {"zh-CN": 57, "en": 57}
    assert all(case["assert"] == [{"type": "python", "value": "file://assert_retrieval.py"}] for case in cases)
    for expected in (
        'corpus_path: "marketplace_qna_corpus.jsonl"',
        'embedding_provider: "gemini"',
        'embedding_model: "gemini-embedding-2"',
        "embedding_dim: 256",
        "rag_chunk_size: 400",
        "rag_chunk_overlap: 80",
        "retrieval_top_k: 5",
    ):
        assert expected in config


def test_marketplace_qna_golden_query_audit_reports_full_coverage():
    from tests.rag_eval.marketplace_qna_golden_query_audit import build_audit_report

    report = build_audit_report()

    assert report["status"] == "passed"
    assert report["counts"] == {
        "source_documents": 18,
        "golden_queries": 114,
        "review_rows": 114,
        "chat_cases": 18,
        "source_questions": 114,
    }
    assert report["gaps"] == {
        "missing_query_ids": [],
        "unexpected_query_ids": [],
        "missing_review_ids": [],
        "unknown_document_ids": [],
        "missing_topic_groups": [],
        "invalid_source_evidence": [],
    }


@pytest.mark.asyncio
async def test_rag_eval_provider_ingests_large_corpora_in_bounded_document_batches():
    from tests.rag_eval.provider import _ingest_corpus

    class RecordingRetriever:
        def __init__(self) -> None:
            self.calls: list[list[str]] = []

        async def ingest(self, docs: list[dict]) -> int:
            self.calls.append([doc["id"] for doc in docs])
            return len(docs)

    retriever = RecordingRetriever()
    docs = [{"id": f"doc-{index}", "text": "body"} for index in range(5)]

    ingested = await _ingest_corpus(retriever, docs, batch_size=2)

    assert ingested == 5
    assert retriever.calls == [["doc-0", "doc-1"], ["doc-2", "doc-3"], ["doc-4"]]


def test_rag_eval_provider_filters_bilingual_corpus_by_case_language():
    from tests.rag_eval.provider import _filter_corpus_docs

    docs = [
        {"id": "zh", "text": "中文", "meta": {"language": "zh-CN"}},
        {"id": "en", "text": "English", "meta": {"language": "en"}},
    ]

    assert _filter_corpus_docs(docs, {"language": "zh-CN"}) == [docs[0]]
    assert _filter_corpus_docs(docs, {"language": "en"}) == [docs[1]]
    assert _filter_corpus_docs(docs, {}) == docs
