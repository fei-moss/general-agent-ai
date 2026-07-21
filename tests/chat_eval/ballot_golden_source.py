"""Lossless adapter from the approved Governance preset Markdown to source rows.

The output is intentionally fed into the existing approved Golden Case workflow;
this module does not define a second ingestion or evaluation contract.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


_QUESTION_HEADING = re.compile(r"^###\s+Q(?P<number>\d+)[：:]\s*(?P<body>.+?)\s*$")
_ANSWER_LABEL = re.compile(r"^\*\*(?P<locale>CN|EN)\*\*[：:]\s*(?P<body>.*)$")
_VARIABLE = re.compile(r"\\?\{(?P<name>[^{}]+?)\\?\}")
_AREAS = {
    1: "ballot_basic_understanding",
    2: "ballot_basic_understanding",
    3: "ballot_basic_understanding",
    4: "ballot_yield_and_airdrop",
    5: "ballot_yield_and_airdrop",
    6: "ballot_yield_and_airdrop",
    7: "ballot_governance_mechanism",
    8: "ballot_governance_mechanism",
    9: "ballot_governance_mechanism",
    10: "ballot_governance_mechanism",
    11: "ballot_governance_mechanism",
    12: "ballot_governance_mechanism",
    13: "ballot_exit_and_safety",
    14: "ballot_exit_and_safety",
    15: "ballot_governance_mechanism",
    16: "ballot_yield_and_airdrop",
    17: "ballot_yield_and_airdrop",
    18: "ballot_trust_and_concentration",
}
_RISKS = {
    1: "medium",
    2: "high",
    3: "high",
    4: "high",
    5: "critical",
    6: "high",
    7: "high",
    8: "high",
    9: "high",
    10: "high",
    11: "high",
    12: "high",
    13: "critical",
    14: "critical",
    15: "high",
    16: "high",
    17: "high",
    18: "high",
}
_STABLE_FACT_TERMS = {
    1: {"zh": [["治理 agent", "治理 Agent"], ["治理投票"], ["项目动态"]], "en": [["governance agent"], ["governance"], ["updates"]]},
    2: {"zh": [["固定收益率"], ["空投"], ["治理投票权"]], "en": [["fixed APY"], ["Airdrop"], ["Governance voting power"]]},
    3: {"zh": [["价格敞口"], ["治理参与"], ["链上可验证"]], "en": [["price exposure"], ["governance"], ["verifiable onchain"]]},
    4: {"zh": [["份额规模"], ["持有时长"], ["年化"]], "en": [["share size"], ["holding duration"], ["annualized"]]},
    5: {"zh": [["项目方提供"], ["合约"], ["可持续性"]], "en": [["project"], ["contract"], ["sustainability"]]},
    6: {"zh": [["持有期间持续累积"], ["Redeem"], ["本金"]], "en": [["accumulate while you hold"], ["redeem"], ["Principal"]]},
    7: {"zh": [["提案"], ["持有者投票"]], "en": [["propose"], ["holders vote"]]},
    8: {"zh": [["快照时点"], ["份额"]], "en": [["snapshot"], ["shares"]]},
    9: {"zh": [["持仓记录"], ["资格与权重"]], "en": [["record of holdings"], ["eligibility and weight"]]},
    10: {"zh": [["提案页"], ["签名提交"], ["上链可查"]], "en": [["proposal page"], ["sign"], ["recorded onchain"]]},
    11: {"zh": [["治理"], ["奖励"]], "en": [["governance"], ["reward"]]},
    12: {"zh": [["链上"], ["链下"]], "en": [["onchain"], ["offchain"]]},
    13: {"zh": [["Redeem"], ["本金"], ["固定收益"], ["空投"]], "en": [["Redeem"], ["principal"], ["fixed yield"], ["airdrops"]]},
    14: {"zh": [["智能合约托管"], ["本金"]], "en": [["smart contract"], ["principal"]]},
    15: {"zh": [["快照"], ["Redeem", "赎回"]], "en": [["snapshot"], ["redeem"]]},
    16: {"zh": [["发起时设定"], ["合约执行"]], "en": [["set and disclosed at launch"], ["enforced by contract"]]},
    17: {"zh": [["固定收益"], ["空投"], ["Redeem"]], "en": [["Fixed yield"], ["airdrops"], ["redemption"]]},
    18: {"zh": [["Top holders"], ["钱包占比"], ["权力分布"]], "en": [["Top holders"], ["stake"], ["power distribution"]]},
}
_FORBIDDEN = {
    5: {"zh": ["保证长期可持续"], "en": ["guarantee long-term sustainability"]},
    11: {"zh": ["投票一定有额外奖励"], "en": ["voting always earns extra rewards"]},
    14: {"zh": ["项目方可以动用本金"], "en": ["the project can use your principal"]},
    18: {"zh": ["项目方不会操纵投票"], "en": ["the project cannot manipulate voting"]},
}


@dataclass(frozen=True)
class ParsedBallotGoldenSource:
    rows: list[dict[str, Any]]
    blockers: list[str]


def parse_ballot_golden_markdown(
    path: Path,
    *,
    excluded_question_ids: set[int] | None = None,
) -> ParsedBallotGoldenSource:
    """Parse paired CN/EN Q&A blocks without rewriting their text."""
    excluded_question_ids = excluded_question_ids or set()
    lines = path.read_text(encoding="utf-8").splitlines()
    starts = [index for index, line in enumerate(lines) if _QUESTION_HEADING.match(line)]
    rows: list[dict[str, Any]] = []
    blockers: list[str] = []
    for position, start in enumerate(starts):
        match = _QUESTION_HEADING.match(lines[start])
        assert match is not None
        number = int(match.group("number"))
        if number in excluded_question_ids:
            continue
        end = starts[position + 1] if position + 1 < len(starts) else len(lines)
        body = match.group("body")
        if "/" not in body:
            blockers.append(f"Q{number}: bilingual questions missing")
            continue
        question_zh, question_en = (part.strip() for part in body.split("/", 1))
        answers = _answers(lines[start + 1 : end])
        if not answers.get("CN") or not answers.get("EN"):
            blockers.append(f"Q{number}: ideal answers missing")
            continue
        if number not in _AREAS or number not in _STABLE_FACT_TERMS:
            blockers.append(f"Q{number}: case metadata missing")
            continue
        for locale, question, answer in (
            ("zh", question_zh, answers["CN"]),
            ("en", question_en, answers["EN"]),
        ):
            variables = list(
                dict.fromkeys(
                    variable.group("name").replace("\\", "")
                    for variable in _VARIABLE.finditer(question + "\n" + answer)
                )
            )
            rows.append(
                {
                    "id": f"ballot_governance_q{number:02d}_{locale}",
                    "source_question_id": f"Q{number}",
                    "question": question,
                    "ideal_answer": answer,
                    "locale": locale,
                    "area": _AREAS[number],
                    "required_fact_groups": _STABLE_FACT_TERMS[number][locale],
                    "forbidden_claims": _FORBIDDEN.get(number, {}).get(locale, []),
                    "requires_rag": True,
                    "requires_tool": "marketplace_agent_context" if variables else None,
                    "risk_level": _RISKS[number],
                    "quality_axes": [
                        "correctness",
                        "completeness",
                        "data_faithfulness",
                        "language_consistency",
                    ],
                    "applicable_agent_types": ["ballot"],
                    **(
                        {
                            "dynamic_fact_variables": variables,
                            "dynamic_fact_rules": variables,
                        }
                        if variables
                        else {}
                    ),
                    "tags": [
                        "ballot",
                        "governance",
                        _AREAS[number],
                        locale,
                    ],
                }
            )
    return ParsedBallotGoldenSource(rows=rows, blockers=blockers)


def _answers(lines: list[str]) -> dict[str, str]:
    output: dict[str, str] = {}
    current: str | None = None
    chunks: list[str] = []

    def finish() -> None:
        nonlocal chunks
        if current is not None:
            while chunks and not chunks[-1].strip():
                chunks.pop()
            output[current] = "\n".join(chunks).strip()
        chunks = []

    for line in lines:
        label = _ANSWER_LABEL.match(line)
        if label:
            finish()
            current = label.group("locale")
            chunks = [label.group("body")]
            continue
        if current is not None and line.startswith("#"):
            finish()
            current = None
            continue
        if current is not None:
            chunks.append(line)
    finish()
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--exclude-question", type=int, action="append", default=[])
    args = parser.parse_args()
    parsed = parse_ballot_golden_markdown(
        args.input,
        excluded_question_ids=set(args.exclude_question),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in parsed.rows
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {"rows": len(parsed.rows), "blockers": parsed.blockers},
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 1 if parsed.blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
