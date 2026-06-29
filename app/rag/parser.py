"""Phase-1 text and Markdown parsing for RAG ingestion."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ParsedDocument:
    """Normalized text document passed to the chunking stage."""

    text: str
    metadata: dict = field(default_factory=dict)


def parse_text_document(
    content: str,
    *,
    mime_type: str | None = None,
    metadata: dict | None = None,
) -> ParsedDocument:
    """Parse phase-1 text-like content.

    Binary formats, URLs, object storage pointers, and OCR are intentionally out
    of scope. Unsupported MIME types fail before any embedding work is done.
    """

    text = (content or "").strip()
    if not text:
        raise ValueError("content 不能为空")
    if mime_type and not _is_text_like(mime_type):
        raise ValueError(f"unsupported mime_type: {mime_type}")
    return ParsedDocument(text=text, metadata=metadata or {})


def _is_text_like(mime_type: str) -> bool:
    normalized = mime_type.strip().lower()
    return normalized.startswith("text/") or normalized in {
        "application/json",
        "application/x-ndjson",
        "application/markdown",
    }
