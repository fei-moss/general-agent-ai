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
    assert acceptance["gemini_preflight"] == {
        "artifact_path": ".artifacts/release/marketplace_qna_gemini_preflight.json",
        "required_status": "passed",
        "embedding_model": "gemini-embedding-2",
        "embedding_dimension": 256,
    }


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


def test_marketplace_qna_chat_cases_define_deterministic_fact_groups():
    rows = _read_jsonl(EVAL_DIR / "marketplace_qna_chat_cases.jsonl")

    assert len(rows) == 18
    assert all(row["required_fact_groups"] for row in rows)
    assert all(
        alternatives
        for row in rows
        for alternatives in row["required_fact_groups"]
    )
    trading_cases = [row for row in rows if row["document_id"].endswith("_07")]
    assert len(trading_cases) == 2
    assert all("dex" in row["query"].casefold() for row in trading_cases)
    assert all(
        "redeem" in row["query"].casefold() or "赎回" in row["query"]
        for row in trading_cases
    )


def test_marketplace_qna_live_fact_evaluator_accepts_alternatives_and_rejects_claims():
    from tests.rag_eval.marketplace_qna_live_eval import evaluate_answer

    result = evaluate_answer(
        "Moss is non-custodial, so your private key stays in your own wallet.",
        required_fact_groups=[
            ["non-custodial", "does not custody"],
            ["private key", "wallet"],
        ],
        forbidden_claims=["Moss guarantees no loss"],
    )
    forbidden = evaluate_answer(
        "Moss guarantees no loss.",
        required_fact_groups=[["non-custodial"]],
        forbidden_claims=["guarantees no loss"],
    )

    assert result == {
        "passed": True,
        "fact_groups": [True, True],
        "forbidden_claims": [],
    }
    assert forbidden["passed"] is False
    assert forbidden["fact_groups"] == [False]
    assert forbidden["forbidden_claims"] == ["guarantees no loss"]


def test_marketplace_qna_fat_chat_fact_accepts_no_prior_knowledge_wording():
    from tests.rag_eval.marketplace_qna_live_eval import evaluate_answer

    case = next(
        row
        for row in _read_jsonl(EVAL_DIR / "marketplace_qna_chat_cases.jsonl")
        if row["id"] == "marketplace_qna_en_01_q01"
    )

    result = evaluate_answer(
        "Moss is built on FAT Protocol. You can use Moss without any prior "
        "knowledge of the FAT Protocol.",
        required_fact_groups=case["required_fact_groups"],
        forbidden_claims=case["forbidden_claims"],
    )

    assert result["passed"] is True


def test_marketplace_qna_fact_matching_allows_ordered_english_modifiers():
    from tests.rag_eval.marketplace_qna_live_eval import evaluate_answer

    result = evaluate_answer(
        "There is no unified platform-wide minimum threshold. The exact price "
        "is shown on the Agent detail page.",
        required_fact_groups=[
            ["no unified threshold"],
            ["detail page"],
        ],
        forbidden_claims=[],
    )

    assert result["passed"] is True


def test_marketplace_qna_fact_matching_does_not_join_unrelated_sentences():
    from tests.rag_eval.marketplace_qna_live_eval import evaluate_answer

    result = evaluate_answer(
        "There is no platform fee. A unified minimum threshold applies.",
        required_fact_groups=[["no unified threshold"]],
        forbidden_claims=[],
    )

    assert result["passed"] is False


def test_marketplace_qna_early_user_fact_accepts_equivalent_not_announced_wording():
    from tests.rag_eval.marketplace_qna_live_eval import evaluate_answer

    case = next(
        row
        for row in _read_jsonl(EVAL_DIR / "marketplace_qna_chat_cases.jsonl")
        if row["id"] == "marketplace_qna_zh_cn_09_q01"
    )
    result = evaluate_answer(
        "早期用户暂时没有公布任何特殊待遇，后续会通过官方渠道发布。",
        required_fact_groups=case["required_fact_groups"],
        forbidden_claims=case["forbidden_claims"],
    )

    assert result["passed"] is True


def test_marketplace_qna_early_user_fact_accepts_currently_not_published_wording():
    from tests.rag_eval.marketplace_qna_live_eval import evaluate_answer

    case = next(
        row
        for row in _read_jsonl(EVAL_DIR / "marketplace_qna_chat_cases.jsonl")
        if row["id"] == "marketplace_qna_zh_cn_09_q01"
    )
    result = evaluate_answer(
        "目前还没有公布任何特殊待遇，尚未推出专项计划；后续会通过官方渠道发布。",
        required_fact_groups=case["required_fact_groups"],
        forbidden_claims=case["forbidden_claims"],
    )

    assert result["passed"] is True


def test_marketplace_qna_fundraising_fact_accepts_actual_trades_wording():
    from tests.rag_eval.marketplace_qna_live_eval import evaluate_answer

    case = next(
        row
        for row in _read_jsonl(EVAL_DIR / "marketplace_qna_chat_cases.jsonl")
        if row["id"] == "marketplace_qna_en_06_q01"
    )
    result = evaluate_answer(
        "Investors mint shares, and the executor executes actual trades "
        "according to the strategy.",
        required_fact_groups=case["required_fact_groups"],
        forbidden_claims=case["forbidden_claims"],
    )

    assert result["passed"] is True


def test_marketplace_qna_live_retrieval_evaluator_requires_uri_language_and_no_degrade():
    from tests.rag_eval.marketplace_qna_live_eval import evaluate_retrieval_response

    response = {
        "degraded": False,
        "chunks": [
            {
                "citation": {"source_uri": "urn:moss:marketplace-qna:en:01"},
                "metadata": {"language": "en"},
            }
        ],
    }
    passed = evaluate_retrieval_response(
        response,
        expected_source_uri="urn:moss:marketplace-qna:en:01",
        language="en",
    )
    wrong_language = evaluate_retrieval_response(
        response,
        expected_source_uri="urn:moss:marketplace-qna:en:01",
        language="zh-CN",
    )
    degraded = evaluate_retrieval_response(
        {**response, "degraded": True},
        expected_source_uri="urn:moss:marketplace-qna:en:01",
        language="en",
    )

    assert passed == {"passed": True, "matched_rank": 1, "degraded": False}
    assert wrong_language["passed"] is False
    assert wrong_language["matched_rank"] is None
    assert degraded["passed"] is False


def test_marketplace_qna_live_chat_payload_uses_server_default_knowledge_base():
    from tests.rag_eval.marketplace_qna_live_eval import build_chat_payload

    payload = build_chat_payload(
        case_id="marketplace_qna_en_01_q01",
        query="How are Moss and FAT related?",
    )

    serialized = json.dumps(payload, sort_keys=True)
    assert "knowledge_base_id" not in serialized
    assert "admin" not in serialized.casefold()
    assert payload["stream"] is True


def test_marketplace_qna_live_report_redacts_runtime_identities_and_secrets():
    from tests.rag_eval.marketplace_qna_live_eval import sanitize_evidence

    evidence = sanitize_evidence(
        {
            "authorization": "Bearer super-secret-admin-token",
            "user": "sensitive-runtime-user",
            "wallet": "sensitive-runtime-wallet",
            "answer_preview": "safe answer",
        },
        sensitive_values={
            "super-secret-admin-token",
            "sensitive-runtime-user",
            "sensitive-runtime-wallet",
        },
    )

    serialized = json.dumps(evidence, sort_keys=True)
    assert "super-secret-admin-token" not in serialized
    assert "sensitive-runtime-user" not in serialized
    assert "sensitive-runtime-wallet" not in serialized
    assert "safe answer" in serialized


def test_marketplace_qna_live_stream_failure_falls_back_without_long_retry():
    from tests.rag_eval.marketplace_qna_live_eval import collect_stream_events_once

    calls = 0

    def failing_get(url: str, headers: dict[str, str], timeout_s: float):
        nonlocal calls
        calls += 1
        raise RuntimeError("transient SSE disconnect")

    events = collect_stream_events_once(
        "https://example.test/stream/run-1",
        {},
        0.1,
        get=failing_get,
    )

    assert events == []
    assert calls == 1


def _write_marketplace_acceptance_evidence(root: Path) -> None:
    contract = json.loads(
        (EVAL_DIR / "marketplace_qna_acceptance_evidence_contract.json").read_text(
            encoding="utf-8"
        )
    )

    def artifact_path(section: str) -> str:
        return contract[section].get("artifact_path") or contract[section][
            "summary_artifact_path"
        ]

    def write(section: str, payload: dict) -> None:
        path = root / artifact_path(section)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    write(
        "fixture_audit",
        {
            "status": "passed",
            "counts": {
                "source_documents": 18,
                "golden_queries": 114,
                "review_rows": 114,
                "chat_cases": 18,
                "source_questions": 114,
            },
            "errors": [],
        },
    )
    write(
        "gemini_preflight",
        {
            "status": "passed",
            "embedding_model": "gemini-embedding-2",
            "embedding_dimension": 256,
            "http_status": 200,
        },
    )
    write(
        "ingestion",
        {
            "submitted_documents": 18,
            "persisted_documents": 18,
            "succeeded_jobs": 18,
            "failed_jobs": 0,
            "persisted_chunks": 141,
            "embedding_provider": "gemini",
            "embedding_model": "gemini-embedding-2",
            "embedding_dim": 256,
            "source_hash_audit": {"hash_maps_equal": True},
        },
    )
    write(
        "promptfoo",
        {
            "results": {
                "stats": {"successes": 114, "failures": 0, "errors": 0},
                "results": [
                    {
                        "response": {
                            "output": json.dumps(
                                {"hits": [{"rank": 1, "doc_id": f"doc{index}"}]}
                            )
                        },
                        "testCase": {
                            "vars": {"relevant_doc_ids": f"doc{index}"}
                        },
                    }
                    for index in range(114)
                ],
            }
        },
    )
    write(
        "live_retrieval",
        {
            "status": "passed",
            "counts": {
                "total": 114,
                "passed": 114,
                "failed": 0,
                "top1": 92,
                "degraded": 0,
            },
            "top1_rate": 92 / 114,
            "results": [
                {"case_id": f"q{index}", "passed": True, "matched_rank": 1}
                for index in range(114)
            ],
        },
    )
    write(
        "live_chat",
        {
            "status": "passed",
            "server_default_knowledge_base": True,
            "counts": {"total": 18, "passed": 18, "failed": 0},
            "results": [
                {
                    "case_id": f"chat{index}",
                    "passed": True,
                    "terminal_status": "SUCCEEDED",
                    "retrieval_started": True,
                    "retrieval_finished": True,
                    "fact_groups": [True],
                    "forbidden_claims": [],
                }
                for index in range(18)
            ],
        },
    )
    write("release_gate", {"overall": "passed"})


def test_marketplace_qna_acceptance_validator_accepts_complete_evidence(tmp_path):
    from tests.rag_eval.marketplace_qna_acceptance_validator import validate_acceptance

    _write_marketplace_acceptance_evidence(tmp_path)

    assert validate_acceptance(root=tmp_path) == []


def test_marketplace_qna_acceptance_validator_reports_every_threshold(tmp_path):
    from tests.rag_eval.marketplace_qna_acceptance_validator import validate_acceptance

    _write_marketplace_acceptance_evidence(tmp_path)
    contract = json.loads(
        (EVAL_DIR / "marketplace_qna_acceptance_evidence_contract.json").read_text(
            encoding="utf-8"
        )
    )

    def load(section: str) -> tuple[Path, dict]:
        artifact_path = contract[section].get("artifact_path") or contract[section][
            "summary_artifact_path"
        ]
        path = tmp_path / artifact_path
        return path, json.loads(path.read_text(encoding="utf-8"))

    path, payload = load("fixture_audit")
    payload["status"] = "failed"
    path.write_text(json.dumps(payload), encoding="utf-8")
    path, payload = load("gemini_preflight")
    payload["status"] = "blocked"
    path.write_text(json.dumps(payload), encoding="utf-8")
    path, payload = load("ingestion")
    payload["failed_jobs"] = 1
    payload["source_hash_audit"]["hash_maps_equal"] = False
    path.write_text(json.dumps(payload), encoding="utf-8")
    path, payload = load("promptfoo")
    payload["results"]["stats"] = {"successes": 113, "failures": 1, "errors": 0}
    path.write_text(json.dumps(payload), encoding="utf-8")
    path, payload = load("live_retrieval")
    payload["counts"].update({"passed": 113, "failed": 1, "degraded": 1})
    payload["top1_rate"] = 0.79
    path.write_text(json.dumps(payload), encoding="utf-8")
    path, payload = load("live_chat")
    payload["counts"].update({"passed": 17, "failed": 1})
    payload["results"][0]["retrieval_finished"] = False
    path.write_text(json.dumps(payload), encoding="utf-8")
    path, payload = load("release_gate")
    payload["overall"] = "failed"
    path.write_text(json.dumps(payload), encoding="utf-8")

    errors = validate_acceptance(root=tmp_path)

    assert any("fixture_audit" in error for error in errors)
    assert any("gemini_preflight" in error for error in errors)
    assert any("failed_jobs" in error for error in errors)
    assert any("source hashes" in error for error in errors)
    assert any("promptfoo" in error for error in errors)
    assert any("live_retrieval" in error and "passed" in error for error in errors)
    assert any("top1_rate" in error for error in errors)
    assert any("degraded" in error for error in errors)
    assert any("live_chat" in error and "passed" in error for error in errors)
    assert any("retrieval evidence" in error for error in errors)
    assert any("release_gate" in error for error in errors)


def test_marketplace_qna_review_and_runbook_cover_cases_and_corpus_defect():
    golden = _read_jsonl(EVAL_DIR / "marketplace_qna_golden_queries.jsonl")
    review = (Path(__file__).parents[1] / "docs/MARKETPLACE_QNA_GOLDEN_QUERIES_REVIEW.md").read_text(
        encoding="utf-8"
    )
    runbook = (Path(__file__).parents[1] / "docs/MARKETPLACE_QNA_RAG_INGESTION_RUNBOOK.md").read_text(
        encoding="utf-8"
    )

    assert all(row["id"] in review for row in golden)
    assert "CORPUS-MPQNA-001" in review
    assert "08_安全与风险.md:43" in review
    assert "make marketplace-qna-live" in runbook
    assert "make marketplace-qna-final" in runbook
    assert "RAG_DEFAULT_KNOWLEDGE_BASE_ID" in runbook
