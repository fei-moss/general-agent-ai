from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


EVAL_DIR = Path(__file__).parent / "rag_eval"


def test_rag_eval_fixtures_are_sanitized_and_well_formed():
    corpus_rows = _read_jsonl(EVAL_DIR / "corpus.jsonl")
    query_rows = _read_jsonl(EVAL_DIR / "golden_queries.jsonl")

    assert len(corpus_rows) >= 3
    assert len(query_rows) >= 3
    assert {row["id"] for row in corpus_rows} >= {
        doc_id
        for query in query_rows
        for doc_id in query["relevant_doc_ids"]
    }
    serialized = json.dumps(corpus_rows + query_rows)
    assert "sk-" not in serialized
    assert "AQ." not in serialized
    assert "Bearer " not in serialized


def test_promptfoo_test_generator_points_to_python_assertion():
    from tests.rag_eval.test_cases import generate_tests

    cases = generate_tests()

    assert len(cases) >= 3
    for case in cases:
        assert case["vars"]["query"]
        assert case["vars"]["relevant_doc_ids"]
        assert case["assert"][0] == {
            "type": "python",
            "value": "file://assert_retrieval.py",
        }


def test_moss_promptfoo_test_generator_points_to_python_assertion():
    from tests.rag_eval.moss_test_cases import generate_tests

    cases = generate_tests()

    assert len(cases) >= 20
    for case in cases:
        assert case["description"].startswith("moss_")
        assert case["vars"]["query"]
        assert case["vars"]["relevant_doc_ids"]
        assert case["assert"][0] == {
            "type": "python",
            "value": "file://assert_retrieval.py",
        }


def test_moss_promptfoo_generator_loads_from_promptfoo_file_wrapper():
    script = """
import importlib.util
from pathlib import Path

path = Path("moss_test_cases.py").resolve()
spec = importlib.util.spec_from_file_location("promptfoo_moss_test_cases", path)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)
cases = module.generate_tests()
assert len(cases) >= 20
"""

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=EVAL_DIR,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr


def test_moss_golden_queries_have_review_evidence():
    query_rows = _read_jsonl(EVAL_DIR / "moss_golden_queries.jsonl")
    review_rows = _read_jsonl(EVAL_DIR / "moss_golden_query_review.jsonl")
    corpus_doc_ids = {row["id"] for row in _read_jsonl(EVAL_DIR / "moss_corpus.jsonl")}
    moss_queries = [row for row in query_rows if row["id"].startswith("moss_")]
    review_by_id = {row["id"]: row for row in review_rows}
    serialized = json.dumps(query_rows + review_rows)

    assert len(moss_queries) >= 20
    assert set(review_by_id) == {row["id"] for row in moss_queries}
    assert "sk-" not in serialized
    assert "AQ." not in serialized
    assert "Bearer " not in serialized

    challenge_types = {row["challenge_type"] for row in review_rows}
    assert len(challenge_types) >= 8

    for query in moss_queries:
        assert set(query["relevant_doc_ids"]) <= corpus_doc_ids
        review = review_by_id[query["id"]]
        assert review["expected_doc_ids"] == query["relevant_doc_ids"]
        assert review["review_reason"]
        assert review["source_evidence"]
        for evidence in review["source_evidence"]:
            assert evidence["source_url"].startswith("https://moss-5.gitbook.io/moss")
            assert evidence["source_lines"]
            assert evidence["claim"]


def test_moss_golden_queries_satisfy_screening_coverage_contract():
    query_rows = _read_jsonl(EVAL_DIR / "moss_golden_queries.jsonl")
    review_rows = _read_jsonl(EVAL_DIR / "moss_golden_query_review.jsonl")
    corpus_rows = _read_jsonl(EVAL_DIR / "moss_corpus.jsonl")
    contract = json.loads((EVAL_DIR / "moss_coverage_contract.json").read_text(encoding="utf-8"))

    query_ids = {row["id"] for row in query_rows}
    tags = {tag for row in query_rows for tag in row.get("tags", [])}
    challenge_types = {row["challenge_type"] for row in review_rows}
    multi_source_query_count = sum(1 for row in query_rows if len(row["relevant_doc_ids"]) > 1)

    assert len(query_rows) >= contract["min_query_count"]
    assert len(corpus_rows) >= contract["min_corpus_doc_count"]
    assert len(challenge_types) >= contract["min_challenge_type_count"]
    assert multi_source_query_count >= contract["min_multi_source_queries"]
    assert set(contract["required_language_tags"]) <= tags
    assert set(contract["required_topic_tags"]) <= tags
    assert set(contract["required_challenge_types"]) <= challenge_types

    for group in contract["capability_groups"]:
        assert group["name"]
        assert set(group["query_ids"]) <= query_ids


def test_moss_rag_seed_manifest_matches_reviewed_fixtures():
    manifest = json.loads((EVAL_DIR / "moss_rag_seed_manifest.json").read_text(encoding="utf-8"))

    assert manifest["spec_id"] == "SPEC-RAG-EVAL-001"
    assert manifest["coverage_contract_id"] == "SPEC-RAG-EVAL-001-MOSS-COVERAGE"
    assert manifest["knowledge_base"]["source_root_url"] == "https://moss-5.gitbook.io/moss"
    assert manifest["embedding_target"] == {
        "provider": "gemini",
        "model": "gemini-embedding-2",
        "dimension": 256,
        "requires_allowed_network": True,
    }

    roles = {source["role"]: source for source in manifest["source_files"]}
    assert set(roles) == {
        "corpus",
        "golden_queries",
        "review_evidence",
        "coverage_contract",
    }
    for source in manifest["source_files"]:
        path = Path(__file__).parents[1] / source["path"]
        assert path.exists()
        assert _sha256(path) == source["sha256"]
        if source["row_count"] is not None:
            assert len(_read_jsonl(path)) == source["row_count"]


def test_moss_acceptance_evidence_contract_matches_seed_and_eval_fixtures():
    from tests.rag_eval.moss_test_cases import generate_tests as generate_moss_tests
    from tests.rag_eval.test_cases import generate_tests as generate_baseline_tests

    contract = json.loads(
        (EVAL_DIR / "moss_acceptance_evidence_contract.json").read_text(encoding="utf-8")
    )
    manifest = json.loads((EVAL_DIR / "moss_rag_seed_manifest.json").read_text(encoding="utf-8"))
    corpus_source = next(source for source in manifest["source_files"] if source["role"] == "corpus")

    assert contract["contract_id"] == "SPEC-RAG-EVAL-001-MOSS-ACCEPTANCE-EVIDENCE"
    assert contract["baseline_eval"]["expected_case_count"] == len(generate_baseline_tests())
    assert contract["baseline_eval"]["required_pass_rate"] == 1.0
    assert contract["semantic_eval"]["expected_case_count"] == len(generate_moss_tests())
    assert contract["semantic_eval"]["required_pass_rate"] == 1.0
    assert contract["semantic_eval"]["embedding_provider"] == manifest["embedding_target"]["provider"]
    assert contract["semantic_eval"]["embedding_model"] == manifest["embedding_target"]["model"]
    assert contract["gemini_preflight"]["artifact_path"].endswith("moss_gemini_preflight.json")
    assert contract["gemini_preflight"]["required_status"] == "passed"
    assert contract["gemini_preflight"]["embedding_model"] == manifest["embedding_target"]["model"]
    assert contract["persistent_ingestion"]["expected_document_count"] == corpus_source["row_count"]
    assert contract["persistent_ingestion"]["required_succeeded_jobs"] == corpus_source["row_count"]
    assert contract["persistent_ingestion"]["summary_artifact_path"].endswith(
        "moss_rag_ingestion_summary.json"
    )
    assert contract["smoke_query"]["expected_doc_ids"] == ["moss_product_safety"]
    assert contract["release_gate"]["command"] == "make verify-release"
    assert contract["release_gate"]["artifact_path"] == ".artifacts/release/summary.json"
    for path in [
        contract["baseline_eval"]["config_path"],
        contract["semantic_eval"]["config_path"],
        contract["persistent_ingestion"]["seed_manifest_path"],
    ]:
        assert (Path(__file__).parents[1] / path).exists()


def test_moss_acceptance_validator_accepts_complete_synthetic_evidence(tmp_path):
    from tests.rag_eval.moss_acceptance_validator import validate_acceptance

    contract = json.loads(
        (EVAL_DIR / "moss_acceptance_evidence_contract.json").read_text(encoding="utf-8")
    )
    release_dir = tmp_path / ".artifacts" / "release"
    release_dir.mkdir(parents=True)
    _write_promptfoo_artifact(
        tmp_path / contract["baseline_eval"]["artifact_path"],
        contract["baseline_eval"]["expected_case_count"],
    )
    _write_promptfoo_artifact(
        tmp_path / contract["semantic_eval"]["artifact_path"],
        contract["semantic_eval"]["expected_case_count"],
    )
    (tmp_path / contract["gemini_preflight"]["artifact_path"]).write_text(
        json.dumps(
            {
                "status": contract["gemini_preflight"]["required_status"],
                "http_status": 200,
                "embedding_model": contract["gemini_preflight"]["embedding_model"],
                "embedding_dimension": 256,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    payload_path = tmp_path / contract["persistent_ingestion"]["payload_artifact_path"]
    payload_path.write_text(
        "\n".join(
            json.dumps({"document": index}, sort_keys=True)
            for index in range(contract["persistent_ingestion"]["expected_document_count"])
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / contract["persistent_ingestion"]["summary_artifact_path"]).write_text(
        json.dumps(
            {
                "submitted_documents": contract["persistent_ingestion"]["expected_document_count"],
                "succeeded_jobs": contract["persistent_ingestion"]["required_succeeded_jobs"],
                "failed_jobs": 0,
                "smoke_query": {
                    "degraded": contract["smoke_query"]["must_be_degraded"],
                    "matched_doc_ids": contract["smoke_query"]["expected_doc_ids"],
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (tmp_path / contract["release_gate"]["artifact_path"]).write_text(
        json.dumps({"overall": "passed"}, sort_keys=True),
        encoding="utf-8",
    )

    assert validate_acceptance(root=tmp_path) == []


def test_moss_acceptance_validator_reports_missing_semantic_artifact(tmp_path):
    from tests.rag_eval.moss_acceptance_validator import validate_acceptance

    contract = json.loads(
        (EVAL_DIR / "moss_acceptance_evidence_contract.json").read_text(encoding="utf-8")
    )
    (tmp_path / ".artifacts" / "release").mkdir(parents=True)
    _write_promptfoo_artifact(
        tmp_path / contract["baseline_eval"]["artifact_path"],
        contract["baseline_eval"]["expected_case_count"],
    )
    (tmp_path / contract["release_gate"]["artifact_path"]).write_text(
        json.dumps({"overall": "passed"}, sort_keys=True),
        encoding="utf-8",
    )

    errors = validate_acceptance(root=tmp_path)

    assert any("semantic_eval: missing artifact" in error for error in errors)


def test_moss_acceptance_validator_reports_blocked_gemini_preflight(tmp_path):
    from tests.rag_eval.moss_acceptance_validator import validate_acceptance

    contract = json.loads(
        (EVAL_DIR / "moss_acceptance_evidence_contract.json").read_text(encoding="utf-8")
    )
    (tmp_path / ".artifacts" / "release").mkdir(parents=True)
    _write_promptfoo_artifact(
        tmp_path / contract["baseline_eval"]["artifact_path"],
        contract["baseline_eval"]["expected_case_count"],
    )
    _write_promptfoo_artifact(
        tmp_path / contract["semantic_eval"]["artifact_path"],
        contract["semantic_eval"]["expected_case_count"],
    )
    (tmp_path / contract["gemini_preflight"]["artifact_path"]).write_text(
        json.dumps(
            {
                "status": "blocked",
                "http_status": 403,
                "reason": "API_KEY_IP_ADDRESS_BLOCKED",
                "caller_ip": "203.0.113.10",
                "embedding_model": contract["gemini_preflight"]["embedding_model"],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (tmp_path / contract["release_gate"]["artifact_path"]).write_text(
        json.dumps({"overall": "passed"}, sort_keys=True),
        encoding="utf-8",
    )

    errors = validate_acceptance(root=tmp_path)

    assert any("gemini_preflight: status=blocked" in error for error in errors)


def test_moss_acceptance_status_report_summarizes_current_blockers(tmp_path):
    from tests.rag_eval.moss_acceptance_status import build_acceptance_status

    contract = json.loads(
        (EVAL_DIR / "moss_acceptance_evidence_contract.json").read_text(encoding="utf-8")
    )
    (tmp_path / ".artifacts" / "release").mkdir(parents=True)
    _write_promptfoo_artifact(
        tmp_path / contract["baseline_eval"]["artifact_path"],
        contract["baseline_eval"]["expected_case_count"],
    )
    (tmp_path / contract["gemini_preflight"]["artifact_path"]).write_text(
        json.dumps(
            {
                "status": "blocked",
                "http_status": 403,
                "reason": "API_KEY_IP_ADDRESS_BLOCKED",
                "caller_ip": "203.0.113.10",
                "embedding_model": contract["gemini_preflight"]["embedding_model"],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (tmp_path / contract["release_gate"]["artifact_path"]).write_text(
        json.dumps({"overall": "passed"}, sort_keys=True),
        encoding="utf-8",
    )

    status = build_acceptance_status(root=tmp_path)
    serialized = json.dumps(status)

    assert status["contract_id"] == contract["contract_id"]
    assert status["status"] == "blocked"
    assert status["artifacts"]["baseline_eval"]["status"] == "passed"
    assert status["artifacts"]["gemini_preflight"]["status"] == "blocked"
    assert any("semantic_eval: missing artifact" in blocker for blocker in status["blockers"])
    assert any(command.startswith(".venv/bin/python -m tests.rag_eval.moss_gemini_preflight") for command in status["next_commands"])
    assert "AQ." not in serialized
    assert "x-goog-api-key" not in serialized


def test_moss_gemini_preflight_classifies_ip_restriction_without_secret():
    from tests.rag_eval.moss_gemini_preflight import build_preflight_result

    payload = {
        "error": {
            "code": 403,
            "message": "The provided API key has an IP address restriction.",
            "status": "PERMISSION_DENIED",
            "details": [
                {
                    "@type": "type.googleapis.com/google.rpc.ErrorInfo",
                    "reason": "API_KEY_IP_ADDRESS_BLOCKED",
                    "domain": "googleapis.com",
                    "metadata": {
                        "service": "generativelanguage.googleapis.com",
                        "callerIp": "203.0.113.10",
                    },
                }
            ],
        }
    }

    result = build_preflight_result(
        http_status=403,
        payload=payload,
        embedding_model="gemini-embedding-2",
    )
    serialized = json.dumps(result)

    assert result["status"] == "blocked"
    assert result["reason"] == "API_KEY_IP_ADDRESS_BLOCKED"
    assert result["caller_ip"] == "203.0.113.10"
    assert "AQ." not in serialized
    assert "x-goog-api-key" not in serialized


async def test_moss_rag_seed_can_be_ingested_by_local_retriever():
    from app.core.config import Settings
    from app.rag.retriever import RAGRetriever

    manifest = json.loads((EVAL_DIR / "moss_rag_seed_manifest.json").read_text(encoding="utf-8"))
    corpus_source = next(source for source in manifest["source_files"] if source["role"] == "corpus")
    rows = _read_jsonl(Path(__file__).parents[1] / corpus_source["path"])
    docs = [
        {
            "id": row["id"],
            "text": row["text"],
            "meta": {
                **row.get("meta", {}),
                "rag_seed_manifest_id": manifest["manifest_id"],
            },
        }
        for row in rows
    ]
    retriever = RAGRetriever(
        settings=Settings(
            _env_file=None,
            embedding_provider="hash",
            embedding_model="hash",
            rag_vector_store="memory",
            embedding_dim=256,
        )
    )

    chunk_count = await retriever.ingest(docs)

    assert chunk_count >= len(rows)


def test_moss_import_payload_generator_matches_rag_document_schema():
    from app.core.schemas import RAGDocumentCreate
    from tests.rag_eval.moss_import_payloads import build_document_payloads

    manifest = json.loads((EVAL_DIR / "moss_rag_seed_manifest.json").read_text(encoding="utf-8"))
    corpus_source = next(source for source in manifest["source_files"] if source["role"] == "corpus")
    rows = _read_jsonl(Path(__file__).parents[1] / corpus_source["path"])
    payloads = build_document_payloads(knowledge_base_id="kb_moss")

    assert len(payloads) == len(rows)
    by_doc_id = {payload["metadata"]["doc_id"]: payload for payload in payloads}
    for row in rows:
        payload = by_doc_id[row["id"]]
        parsed = RAGDocumentCreate(**payload)
        assert parsed.knowledge_base_id == "kb_moss"
        assert parsed.content == row["text"]
        assert parsed.source_type == "api"
        assert parsed.source_uri == row["meta"]["source_url"]
        assert parsed.mime_type == "text/plain"
        assert parsed.metadata["source_lines"] == row["meta"]["source_lines"]
        assert parsed.metadata["rag_seed_manifest_id"] == manifest["manifest_id"]
        assert parsed.metadata["coverage_contract_id"] == manifest["coverage_contract_id"]


def test_moss_review_markdown_mentions_every_query_id():
    query_rows = _read_jsonl(EVAL_DIR / "moss_golden_queries.jsonl")
    contract = json.loads((EVAL_DIR / "moss_coverage_contract.json").read_text(encoding="utf-8"))
    review_doc = (Path(__file__).parents[1] / "docs" / "MOSS_GOLDEN_QUERIES_REVIEW.md").read_text(
        encoding="utf-8"
    )

    assert "Review Conclusion" in review_doc
    assert "Capability Coverage" in review_doc
    assert contract["contract_id"] in review_doc
    assert "SPEC-RAG-EVAL-001-MOSS-ACCEPTANCE-EVIDENCE" in review_doc
    for query in query_rows:
        assert query["id"] in review_doc
    for group in contract["capability_groups"]:
        assert group["name"] in review_doc


def test_moss_rag_ingestion_runbook_matches_seed_and_api_flow():
    manifest = json.loads((EVAL_DIR / "moss_rag_seed_manifest.json").read_text(encoding="utf-8"))
    evidence_contract = json.loads(
        (EVAL_DIR / "moss_acceptance_evidence_contract.json").read_text(encoding="utf-8")
    )
    runbook = (Path(__file__).parents[1] / "docs" / "MOSS_RAG_INGESTION_RUNBOOK.md").read_text(
        encoding="utf-8"
    )
    review_doc = (Path(__file__).parents[1] / "docs" / "MOSS_GOLDEN_QUERIES_REVIEW.md").read_text(
        encoding="utf-8"
    )

    assert manifest["manifest_id"] in runbook
    assert manifest["knowledge_base"]["name"] in runbook
    assert manifest["embedding_target"]["provider"] in runbook
    assert manifest["embedding_target"]["model"] in runbook
    assert evidence_contract["contract_id"] in runbook
    assert ".artifacts/release/moss_rag_promptfoo_eval.json" in runbook
    assert evidence_contract["persistent_ingestion"]["payload_artifact_path"] in runbook
    assert evidence_contract["persistent_ingestion"]["summary_artifact_path"] in runbook
    assert evidence_contract["gemini_preflight"]["artifact_path"] in runbook
    assert "tests.rag_eval.moss_import_payloads" in runbook
    assert "tests.rag_eval.moss_gemini_preflight" in runbook
    assert "tests.rag_eval.moss_acceptance_status" in runbook
    assert "tests.rag_eval.moss_golden_query_audit" in runbook
    assert "moss_golden_query_audit.json" in runbook
    assert "moss_rag_acceptance_status.json" in runbook
    assert "embedContent" in runbook
    assert "API_KEY_IP_ADDRESS_BLOCKED" in runbook
    for route in [
        "POST /rag/knowledge-bases",
        "POST /rag/documents",
        "GET /rag/ingestion-jobs/{job_id}",
        "POST /rag/query",
    ]:
        assert route in runbook
    for source in manifest["source_files"]:
        assert source["path"] in runbook
    assert "SHA-256" in runbook
    assert "shasum -a 256" in runbook
    assert "docs/MOSS_RAG_INGESTION_RUNBOOK.md" in review_doc


def test_promptfoo_provider_returns_ranked_hits(monkeypatch):
    from tests.rag_eval.provider import call_api

    monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)
    monkeypatch.delenv("RAG_EVAL_EMBEDDING_PROVIDER", raising=False)

    result = call_api(
        "How do we smoke test pgvector with DockerHost?",
        options={"config": {"corpus_path": "corpus.jsonl", "embedding_provider": "hash"}},
        context={"vars": {"query": "How do we smoke test pgvector with DockerHost?", "top_k": 3}},
    )
    payload = json.loads(result["output"])

    assert payload["degraded"] is False
    assert payload["hits"]
    assert {hit["doc_id"] for hit in payload["hits"]} & {"dockerhost"}
    assert "preview" in payload["hits"][0]


def test_retrieval_assertion_fails_when_expected_doc_is_missing():
    from tests.rag_eval.assert_retrieval import get_assert

    output = json.dumps(
        {
            "degraded": False,
            "hits": [{"rank": 1, "doc_id": "other", "score": 0.99}],
        }
    )

    result = get_assert(
        output,
        {"vars": {"relevant_doc_ids": ["dockerhost"], "max_rank": 1}},
    )

    assert result["pass"] is False
    assert result["score"] == 0


def test_retrieval_assertion_passes_expected_doc_within_rank():
    from tests.rag_eval.assert_retrieval import get_assert

    output = json.dumps(
        {
            "degraded": False,
            "hits": [
                {"rank": 1, "doc_id": "other", "score": 0.88},
                {"rank": 2, "doc_id": "dockerhost", "score": 0.77},
            ],
        }
    )

    result = get_assert(
        output,
        {"vars": {"relevant_doc_ids": ["dockerhost"], "max_rank": 2}},
    )

    assert result["pass"] is True
    assert result["score"] > 0


def test_promptfoo_config_references_existing_files():
    config = (EVAL_DIR / "promptfooconfig.yaml").read_text(encoding="utf-8")

    for filename in [
        "provider.py",
        "test_cases.py",
        "corpus.jsonl",
    ]:
        assert filename in config
        assert (EVAL_DIR / filename).exists()
    assert (EVAL_DIR / "assert_retrieval.py").exists()


def test_moss_promptfoo_config_references_existing_files():
    config = (EVAL_DIR / "moss_promptfooconfig.yaml").read_text(encoding="utf-8")

    for filename in [
        "provider.py",
        "moss_test_cases.py",
        "moss_corpus.jsonl",
    ]:
        assert filename in config
        assert (EVAL_DIR / filename).exists()
    assert "embedding_provider: \"gemini\"" in config
    assert "moss_golden_queries.jsonl" not in config
    assert (EVAL_DIR / "moss_golden_queries.jsonl").exists()
    assert (EVAL_DIR / "moss_golden_query_review.jsonl").exists()
    assert (EVAL_DIR / "moss_coverage_contract.json").exists()
    assert (EVAL_DIR / "moss_rag_seed_manifest.json").exists()
    assert (EVAL_DIR / "assert_retrieval.py").exists()


def test_moss_golden_query_audit_report_proves_review_and_coverage():
    from tests.rag_eval.moss_golden_query_audit import build_audit_report

    query_rows = _read_jsonl(EVAL_DIR / "moss_golden_queries.jsonl")
    corpus_rows = _read_jsonl(EVAL_DIR / "moss_corpus.jsonl")
    review_rows = _read_jsonl(EVAL_DIR / "moss_golden_query_review.jsonl")
    report = build_audit_report()
    serialized = json.dumps(report)

    assert report["status"] == "passed"
    assert report["spec_id"] == "SPEC-RAG-EVAL-001"
    assert report["coverage_contract_id"] == "SPEC-RAG-EVAL-001-MOSS-COVERAGE"
    assert report["counts"]["queries"] == len(query_rows)
    assert report["counts"]["corpus_docs"] == len(corpus_rows)
    assert report["counts"]["review_rows"] == len(review_rows)
    assert report["counts"]["queries_with_source_evidence"] == len(query_rows)
    assert report["provenance"]["review_evidence_count"] >= len(review_rows)
    assert report["provenance"]["corpus_rows_with_source_url"] == len(corpus_rows)
    assert report["provenance"]["corpus_rows_with_source_lines"] == len(corpus_rows)
    assert report["provenance"]["invalid_source_line_ranges"] == []
    assert report["provenance"]["review_source_urls_without_corpus_source_url"] == []
    assert report["coverage"]["required_topic_tags_missing"] == []
    assert report["coverage"]["required_challenge_types_missing"] == []
    assert report["coverage"]["capability_groups_missing_queries"] == []
    assert report["screening_value"]["multi_source_query_count"] >= 2
    assert report["screening_value"]["challenge_type_count"] >= 10
    assert "AQ." not in serialized
    assert "Bearer " not in serialized
    assert "sk-" not in serialized


def _read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_promptfoo_artifact(path: Path, case_count: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "results": {
                    "stats": {
                        "successes": case_count,
                        "failures": 0,
                        "errors": 0,
                    },
                    "results": [{"success": True} for _ in range(case_count)],
                }
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
