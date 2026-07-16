from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


SOURCE_ROOT = Path(__file__).parent / "marketplace_qna_sources"
EXPECTED_QUESTION_COUNTS = (5, 7, 2, 16, 4, 9, 4, 7, 3)
_QUESTION_RE = re.compile(r"^\*\*Q[:：]\s*(.+?)\*\*\s*$")


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


def _language_slug(language: str) -> str:
    return language.lower().replace("-", "_")


def _source_specs() -> tuple[SourceSpec, ...]:
    specs: list[SourceSpec] = []
    for language in ("zh-CN", "en"):
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
                    source_uri=f"marketplace-qna://{language}/{path.name}",
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
