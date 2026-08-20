from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SOURCE_ROOT = Path(__file__).parent / "marketplace_qna_sources"
CASE_DEFINITIONS_PATH = Path(__file__).parent / "marketplace_qna_case_definitions.jsonl"
CORPUS_VERSION = "marketplace-qna-bilingual-2026-08-19-v7"
GENERATED_PATHS = {
    "corpus": Path(__file__).parent / "marketplace_qna_corpus.jsonl",
    "golden_queries": Path(__file__).parent / "marketplace_qna_golden_queries.jsonl",
    "review_evidence": Path(__file__).parent / "marketplace_qna_golden_query_review.jsonl",
    "chat_cases": Path(__file__).parent / "marketplace_qna_chat_cases.jsonl",
}
EXPECTED_QUESTION_COUNTS = (
    5,
    7,
    2,
    16,
    4,
    9,
    4,
    7,
    3,
    18,
    22,
    12,
    12,
    8,
    18,
    11,
)
_QUESTION_RE = re.compile(r"^\*\*Q[:：]\s*(.+?)\*\*\s*$")

# Representative chat cases use deterministic semantic fact groups instead of
# requiring the model to reproduce a full source sentence verbatim. Every
# inner tuple is an OR group; all outer groups must be represented.
CHAT_REQUIRED_FACT_GROUPS: dict[str, tuple[tuple[str, ...], ...]] = {
    "marketplace_qna_en_01": (
        ("FAT Protocol",),
        (
            "do not need",
            "don't need",
            "without studying",
            "without any prior knowledge",
            "no prior knowledge",
            "underlying protocol is abstracted",
        ),
    ),
    "marketplace_qna_en_02": (("fully preserved", "fully retained", "preserved intact", "retained intact"),),
    "marketplace_qna_en_03": (("Perp Trading",), ("Governance",), ("Consumer",)),
    "marketplace_qna_en_04": (("no unified threshold", "no unified minimum", "no universal threshold", "no uniform threshold"), ("detail page",)),
    "marketplace_qna_en_05": (("number of holders", "holder count", "holders"), ("actual trading activity", "real trade records", "trading performance")),
    "marketplace_qna_en_06": (
        ("users invest", "other users", "investors", "participants"),
        (
            "real trading",
            "actual trading",
            "actual trades",
            "executes trades",
            "execute the trading strategy",
        ),
    ),
    "marketplace_qna_en_07": (("DEX", "Trade on DEX"), ("Redeem",)),
    "marketplace_qna_en_08": (("non-custodial", "does not custody", "will not custody"), ("private key", "wallet")),
    "marketplace_qna_en_09": (("not been announced", "not yet announced", "no special treatment", "currently unavailable"), ("official channels", "@MossAI_Official")),
    "marketplace_qna_en_10": (
        ("Governance Agent",),
        ("current Agent context", "current Agent configuration", "current Agent data"),
        ("fixed-yield accrual", "fixed yield"),
    ),
    "marketplace_qna_en_11": (
        ("settlement data", "incorrect settlement"),
        ("orders in the Agent's name", "reckless orders"),
        ("cannot leave", "cannot be moved out", "cannot send funds to an arbitrary address"),
    ),
    "marketplace_qna_en_12": (
        ("snapshot",),
        ("proposal went live", "proposal creation", "proposal is created"),
        ("holdings", "held", "shares"),
    ),
    "marketplace_qna_en_13": (
        ("Consumer Agent",),
        ("benefits supplied by the brand", "brand benefits"),
        ("shares",),
        ("redeem a code", "redemption code"),
        ("Refund", "recover their current principal value"),
    ),
    "marketplace_qna_en_14": (
        ("Redeem",),
        ("shares are consumed", "corresponding shares are consumed"),
        ("generates a code",),
    ),
    "marketplace_qna_en_15": (
        ("still held", "held by the user"),
        ("not yet redeemed", "unredeemed"),
        ("Refund",),
    ),
    "marketplace_qna_en_16": (
        ("AI video generation company",),
        ("video foundation models",),
        ("text-to-video",),
        ("image-to-video",),
        ("Marketing Hub",),
        ("Canvas",),
        ("CLI",),
    ),
    "marketplace_qna_zh_cn_01": (("FAT Protocol",), ("不需要", "无需", "不必")),
    "marketplace_qna_zh_cn_02": (("完整保留", "完整迁移", "保留完整"),),
    "marketplace_qna_zh_cn_03": (("Perp Trading", "永续交易"), ("Governance", "治理"), ("Consumer", "消费者")),
    "marketplace_qna_zh_cn_04": (("没有统一门槛", "没有统一的最低", "无统一门槛", "不存在统一"), ("详情页",)),
    "marketplace_qna_zh_cn_05": (("持有人数", "持有者数量", "Holders"), ("实际交易", "交易记录", "交易表现")),
    "marketplace_qna_zh_cn_06": (("Mint", "铸造份额"), ("真实交易", "实际交易")),
    "marketplace_qna_zh_cn_07": (("DEX", "去中心化交易所"), ("Redeem", "赎回")),
    "marketplace_qna_zh_cn_08": (("不托管", "非托管"), ("私钥", "钱包")),
    "marketplace_qna_zh_cn_09": (
        (
            "暂未公布",
            "尚未公布",
            "还未公布",
            "暂时没有公布",
            "目前还没有公布",
            "尚未推出",
            "还没有宣布",
            "尚未宣布",
            "目前无特殊待遇",
        ),
        ("官方渠道", "@MossAI_Official"),
    ),
    "marketplace_qna_zh_cn_10": (
        ("Governance Agent",),
        ("当前 Agent context", "当前 Agent 配置", "当前 Agent 数据"),
        ("固定收益",),
    ),
    "marketplace_qna_zh_cn_11": (
        ("结算数据",),
        ("下单",),
        ("转不出去", "无法转出", "无法将资金转出"),
    ),
    "marketplace_qna_zh_cn_12": (
        ("快照",),
        ("提案创建", "创建时"),
        ("持仓", "份额"),
    ),
    "marketplace_qna_zh_cn_13": (
        ("Consumer Agent",),
        ("品牌方", "品牌权益"),
        ("标准份额", "份额"),
        ("兑换码",),
        ("Refund", "取回当时对应的本金价值"),
    ),
    "marketplace_qna_zh_cn_14": (
        ("去兑换",),
        ("份额被消耗", "相应份额被消耗"),
        ("生成兑换码",),
    ),
    "marketplace_qna_zh_cn_15": (
        ("仍由用户持有", "用户持有"),
        ("尚未兑换", "未兑换"),
        ("Refund",),
    ),
    "marketplace_qna_zh_cn_16": (
        ("AI 视频生成公司",),
        ("视频基础模型",),
        ("文生视频",),
        ("图生视频",),
        ("Marketing Hub",),
        ("Canvas",),
        ("CLI",),
    ),
}
CHAT_QUERY_OVERRIDES = {
    "marketplace_qna_en_10_q01": (
        "What is the core purpose of a Governance Agent whose backend type is "
        "ballot, and which concrete details must come from the current Agent "
        "context or configuration?"
    ),
    "marketplace_qna_en_07_q01": (
        "How can I sell shares that I minted? Explain separately what to do when "
        "the Agent has a DEX trading pair and when it does not, including Redeem."
    ),
    "marketplace_qna_zh_cn_07_q01": (
        "我该如何出售 Mint 的 Agent 份额？请分别说明有 DEX 交易对和没有 DEX "
        "交易对时的处理方式，包括 Redeem（赎回）。"
    ),
    "marketplace_qna_zh_cn_10_q01": (
        "后端类型为 ballot 的 Governance Agent 核心用途是什么？回答时也请说明"
        "哪些具体信息必须来自当前 Agent context 或配置。"
    ),
}


@dataclass(frozen=True)
class SourceSpec:
    path: Path
    language: str
    order: int
    id: str
    source_uri: str


@dataclass(frozen=True)
class QuestionBlock:
    id: str
    document_id: str
    question: str
    answer: str
    question_line: int
    answer_start_line: int
    answer_end_line: int


@dataclass(frozen=True)
class ParsedSource:
    id: str
    path: Path
    filename: str
    language: str
    order: int
    source_uri: str
    text: str
    questions: tuple[QuestionBlock, ...]


@dataclass(frozen=True)
class FixtureBundle:
    sources: tuple[ParsedSource, ...]


@dataclass(frozen=True)
class CaseDefinition:
    id: str
    document_id: str
    language: str
    query: str
    challenge_type: str
    required_facts: tuple[str, ...]
    forbidden_claims: tuple[str, ...]
    representative_chat: bool
    review_reason: str


@dataclass(frozen=True)
class FixtureRows:
    corpus: tuple[dict[str, Any], ...]
    golden_queries: tuple[dict[str, Any], ...]
    review_evidence: tuple[dict[str, Any], ...]
    chat_cases: tuple[dict[str, Any], ...]


def _language_slug(language: str) -> str:
    return language.lower().replace("-", "_")


def _source_specs() -> tuple[SourceSpec, ...]:
    specs: list[SourceSpec] = []
    for language in ("zh-CN", "en"):
        language_key = "cn" if language == "zh-CN" else "en"
        paths = sorted((SOURCE_ROOT / language).glob("*.md"))
        for path in paths:
            prefix, separator, _ = path.name.partition("_")
            if not separator or not prefix.isdigit():
                raise ValueError(f"source filename has no numeric order: {path.name}")
            order = int(prefix)
            document_id = f"marketplace_qna_{_language_slug(language)}_{order:02d}"
            specs.append(
                SourceSpec(
                    path=path,
                    language=language,
                    order=order,
                    id=document_id,
                    source_uri=f"urn:moss:marketplace-qna:{language_key}:{order:02d}",
                )
            )
    return tuple(specs)


def parse_source(path: Path, spec: SourceSpec) -> ParsedSource:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    question_starts: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        match = _QUESTION_RE.match(line)
        if match:
            question_starts.append((index, match.group(1).strip()))

    questions: list[QuestionBlock] = []
    for question_index, (line_index, question) in enumerate(question_starts, start=1):
        next_question_line = (
            question_starts[question_index][0]
            if question_index < len(question_starts)
            else len(lines)
        )
        answer_start = line_index + 1
        while answer_start < next_question_line and not lines[answer_start].strip():
            answer_start += 1
        answer_end_exclusive = next_question_line
        while answer_end_exclusive > answer_start and not lines[answer_end_exclusive - 1].strip():
            answer_end_exclusive -= 1
        answer = "\n".join(lines[answer_start:answer_end_exclusive]).strip()
        if not question or not answer:
            raise ValueError(f"empty question or answer in {path}:{line_index + 1}")
        questions.append(
            QuestionBlock(
                id=f"{spec.id}_q{question_index:02d}",
                document_id=spec.id,
                question=question,
                answer=answer,
                question_line=line_index + 1,
                answer_start_line=answer_start + 1,
                answer_end_line=answer_end_exclusive,
            )
        )

    return ParsedSource(
        id=spec.id,
        path=path,
        filename=path.name,
        language=spec.language,
        order=spec.order,
        source_uri=spec.source_uri,
        text=text,
        questions=tuple(questions),
    )


def build_fixture_bundle() -> FixtureBundle:
    specs = _source_specs()
    sources = tuple(parse_source(spec.path, spec) for spec in specs)
    ids = [source.id for source in sources]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate Marketplace QnA source ids")
    question_ids = [question.id for source in sources for question in source.questions]
    if len(question_ids) != len(set(question_ids)):
        raise ValueError("duplicate Marketplace QnA question ids")
    for language in ("zh-CN", "en"):
        counts = tuple(
            len(source.questions)
            for source in sources
            if source.language == language
        )
        if counts != EXPECTED_QUESTION_COUNTS:
            raise ValueError(
                f"unexpected {language} question counts: {counts}; "
                f"expected {EXPECTED_QUESTION_COUNTS}"
            )
    return FixtureBundle(sources=sources)


def load_case_definitions(
    bundle: FixtureBundle | None = None,
    path: Path = CASE_DEFINITIONS_PATH,
) -> dict[str, CaseDefinition]:
    bundle = bundle or build_fixture_bundle()
    source_by_question = {
        question.id: source
        for source in bundle.sources
        for question in source.questions
    }
    cases: dict[str, CaseDefinition] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        case = CaseDefinition(
            id=str(row["id"]),
            document_id=str(row["document_id"]),
            language=str(row["language"]),
            query=str(row["query"]).strip(),
            challenge_type=str(row["challenge_type"]).strip(),
            required_facts=tuple(str(value).strip() for value in row["required_facts"]),
            forbidden_claims=tuple(str(value).strip() for value in row["forbidden_claims"]),
            representative_chat=bool(row["representative_chat"]),
            review_reason=str(row["review_reason"]).strip(),
        )
        if case.id in cases:
            raise ValueError(f"duplicate case id at {path}:{line_number}: {case.id}")
        source = source_by_question.get(case.id)
        if source is None:
            raise ValueError(f"unknown question id at {path}:{line_number}: {case.id}")
        if case.document_id != source.id or case.language != source.language:
            raise ValueError(f"case source mismatch at {path}:{line_number}: {case.id}")
        cases[case.id] = case
    if set(cases) != set(source_by_question):
        missing = sorted(set(source_by_question) - set(cases))
        unexpected = sorted(set(cases) - set(source_by_question))
        raise ValueError(f"case coverage mismatch: missing={missing}, unexpected={unexpected}")
    return cases


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def build_fixture_rows() -> FixtureRows:
    bundle = build_fixture_bundle()
    cases = load_case_definitions(bundle)
    question_by_id = {
        question.id: question
        for source in bundle.sources
        for question in source.questions
    }
    source_by_id = {source.id: source for source in bundle.sources}

    corpus: list[dict[str, Any]] = []
    for source in bundle.sources:
        corpus.append(
            {
                "id": source.id,
                "text": source.text,
                "meta": {
                    "source": source.source_uri,
                    "source_uri": source.source_uri,
                    "source_path": source.path.relative_to(Path(__file__).parents[2]).as_posix(),
                    "filename": source.filename,
                    "language": source.language,
                    "document_order": source.order,
                    "source_set": CORPUS_VERSION,
                    "corpus_version": CORPUS_VERSION,
                    "sha256": _sha256_bytes(source.text.encode("utf-8")),
                },
            }
        )

    golden_queries: list[dict[str, Any]] = []
    review_evidence: list[dict[str, Any]] = []
    chat_cases: list[dict[str, Any]] = []
    for case_id in sorted(cases):
        case = cases[case_id]
        block = question_by_id[case_id]
        source = source_by_id[case.document_id]
        tags = [
            "marketplace-qna",
            case.language,
            f"topic-{source.order:02d}",
            case.challenge_type,
        ]
        golden_queries.append(
            {
                "id": case.id,
                "query": case.query,
                "relevant_doc_ids": [case.document_id],
                "max_rank": 5,
                "top_k": 5,
                "tags": tags,
            }
        )
        review_evidence.append(
            {
                "id": case.id,
                "expected_doc_ids": [case.document_id],
                "original_question": block.question,
                "challenge_type": case.challenge_type,
                "source_evidence": [
                    {
                        "source_uri": source.source_uri,
                        "source_path": source.path.relative_to(Path(__file__).parents[2]).as_posix(),
                        "source_lines": f"{block.answer_start_line}-{block.answer_end_line}",
                        "claim": case.required_facts[0],
                    }
                ],
                "review_reason": case.review_reason,
            }
        )
        if case.representative_chat:
            required_fact_groups = CHAT_REQUIRED_FACT_GROUPS.get(case.document_id)
            if not required_fact_groups:
                raise ValueError(
                    f"missing chat required fact groups for {case.document_id}"
                )
            chat_cases.append(
                {
                    "id": case.id,
                    "document_id": case.document_id,
                    "language": case.language,
                    "query": CHAT_QUERY_OVERRIDES.get(case.id, case.query),
                    "required_facts": list(case.required_facts),
                    "required_fact_groups": [
                        list(alternatives) for alternatives in required_fact_groups
                    ],
                    "forbidden_claims": list(case.forbidden_claims),
                    "source_uri": source.source_uri,
                }
            )
    return FixtureRows(
        corpus=tuple(corpus),
        golden_queries=tuple(golden_queries),
        review_evidence=tuple(review_evidence),
        chat_cases=tuple(chat_cases),
    )


def _jsonl(rows: tuple[dict[str, Any], ...]) -> str:
    return "\n".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for row in rows
    ) + "\n"


def write_fixture_files() -> None:
    rows = build_fixture_rows()
    for name, path in GENERATED_PATHS.items():
        path.write_text(_jsonl(getattr(rows, name)), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Marketplace QnA RAG evaluation fixtures")
    parser.add_argument("--write", action="store_true", help="write generated JSONL fixture files")
    args = parser.parse_args()
    rows = build_fixture_rows()
    if args.write:
        write_fixture_files()
    print(
        json.dumps(
            {
                "sources": len(rows.corpus),
                "golden_queries": len(rows.golden_queries),
                "review_evidence": len(rows.review_evidence),
                "chat_cases": len(rows.chat_cases),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
