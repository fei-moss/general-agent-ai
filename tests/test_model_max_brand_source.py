from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest


_EVAL_DIR = Path(__file__).parent / "rag_eval"
_VENDORED_SOURCE = (
    Path(__file__).parent / "chat_eval" / "fixtures" / "model_max_brand_intro_20260916.md"
)
_VENDORED_SOURCE_SHA256 = (
    "804c810f8167941da76927d5962c19ee1b7fb7634a8b69b1b6a660c705d53bd4"
)


def _owner_intro(language: str) -> str:
    text = _VENDORED_SOURCE.read_text(encoding="utf-8")
    english, chinese = text.split("EN:\n", 1)[1].split("\n\nZH:\n", 1)
    return (chinese if language == "zh_cn" else english).strip()


def test_model_max_owner_source_is_vendored_verbatim_and_hash_pinned():
    payload = _VENDORED_SOURCE.read_bytes()

    assert hashlib.sha256(payload).hexdigest() == _VENDORED_SOURCE_SHA256
    assert payload.decode("utf-8").startswith(
        "# Owner 素材(2026-09-16):Model Max 品牌简介(consumer Agent #212)\n"
    )


@pytest.mark.parametrize("language", ["zh_cn", "en"])
def test_model_max_document_and_queries_stay_brand_scoped(language):
    from tests.rag_eval.marketplace_qna_fixture_builder import (
        build_fixture_bundle,
        load_case_definitions,
    )

    bundle = build_fixture_bundle()
    document_id = f"marketplace_qna_{language}_18"
    source = {source.id: source for source in bundle.sources}[document_id]
    cases = load_case_definitions(bundle)

    assert len(source.questions) == 5
    assert source.questions[0].answer == _owner_intro(language)
    assert all("Model Max" in question.question for question in source.questions)
    assert all("Model Max" in cases[question.id].query for question in source.questions)
    page_reference = (
        "current Model Max Agent page" if language == "en" else "当前 Model Max Agent 页面"
    )
    assert page_reference in source.text
    assert "typed context" in source.text
    for unapproved_detail in (
        "Refund", "PixVerse", "#212", "USDC", "USDT", "%", "https://", "http://",
    ):
        assert unapproved_detail.casefold() not in source.text.casefold()


@pytest.mark.parametrize("language", ["zh_cn", "en"])
def test_model_max_chat_requires_the_approved_brand_facts(language):
    from tests.rag_eval.marketplace_qna_live_eval import evaluate_answer

    chats = [
        json.loads(line)
        for line in (_EVAL_DIR / "marketplace_qna_chat_cases.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    case = next(row for row in chats if row["document_id"] == f"marketplace_qna_{language}_18")
    arguments = {
        "required_fact_groups": case["required_fact_groups"],
        "forbidden_claims": case["forbidden_claims"],
    }
    answer = _owner_intro(language)

    assert "Model Max" in case["query"]
    assert evaluate_answer(answer, **arguments)["passed"] is True
    assert evaluate_answer(answer.replace("Astra", ""), **arguments)["passed"] is False
    assert evaluate_answer("PixVerse is an AI video generation company.", **arguments)["passed"] is False
