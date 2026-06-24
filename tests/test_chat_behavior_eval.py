"""Data-driven chat behavior eval contract tests."""

from __future__ import annotations

import pytest

from app.runtime.chat_behavior import (
    GuardrailAction,
    GuardrailCategory,
    evaluate_assistant_answer,
    evaluate_user_message,
)
from tests.chat_eval.evaluator import (
    ChatBehaviorCase,
    coverage_summary,
    load_cases,
    validate_cases,
)


@pytest.fixture(scope="module")
def cases() -> list[ChatBehaviorCase]:
    return load_cases()


def test_golden_cases_have_valid_schema(cases):
    assert len(cases) >= 10
    assert validate_cases([case.raw for case in cases]) == []
    assert len({case.id for case in cases}) == len(cases)


def test_golden_cases_cover_required_behavior_axes(cases):
    summary = coverage_summary(cases)

    assert summary["allow"] >= 5
    assert summary["refuse"] >= 4
    assert summary["rag_required"] >= 2
    assert summary["hidden_instruction"] >= 2
    assert summary["secret_request"] >= 2
    assert summary["real_money_operation"] >= 1
    assert summary["output_policy_leak"] >= 1
    assert summary["false_positive_guard"] >= 4


@pytest.mark.parametrize("case", load_cases(), ids=lambda case: case.id)
def test_input_guardrail_matches_golden_cases(case: ChatBehaviorCase):
    decision = evaluate_user_message(case.user_message)

    assert decision.action is GuardrailAction(case.expected_input_action)
    assert decision.category is GuardrailCategory(case.expected_input_category)
    if case.expected_input_action == "refuse":
        for expected in case.raw.get("safe_response_contains", []):
            assert expected in decision.safe_response
        for forbidden in case.raw.get("safe_response_forbids", []):
            assert forbidden not in decision.safe_response
    else:
        assert decision.safe_response == ""


@pytest.mark.parametrize(
    "case",
    [case for case in load_cases() if case.sample_assistant_answer],
    ids=lambda case: case.id,
)
def test_output_guardrail_matches_golden_output_cases(case: ChatBehaviorCase):
    decision = evaluate_assistant_answer(case.sample_assistant_answer or "")

    assert decision.action is GuardrailAction(str(case.raw["expected_output_action"]))
    assert decision.category is GuardrailCategory(
        str(case.raw["expected_output_category"])
    )
    for expected in case.raw.get("safe_response_contains", []):
        assert expected in decision.safe_response
    for forbidden in case.raw.get("safe_response_forbids", []):
        assert forbidden not in decision.safe_response


def test_allowed_cases_define_future_answer_level_oracles(cases):
    allowed = [
        case
        for case in cases
        if case.expected_input_action == GuardrailAction.ALLOW.value
    ]

    assert allowed
    for case in allowed:
        assert case.raw["answer_traits"], case.id
        assert case.raw["forbidden_claims"], case.id
        assert isinstance(case.raw["requires_rag"], bool), case.id
