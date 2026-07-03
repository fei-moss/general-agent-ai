#!/usr/bin/env python3
"""Validate the root production deployment contract."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "production-deployment-contract.md"
RUNBOOK = ROOT / "docs/DOCKERHOST_RELEASE_RUNBOOK.md"

CONTRACT_TERMS = (
    "SPEC-PLATFORM-MECHANISM-ABSORPTION-002",
    "DockerHost Git pull deployment",
    "envctl check-project",
    "envctl validate-template",
    "--secret-env",
    "--secret-file",
    "/healthz",
    "/readyz",
    "STREAM_FALSE_NOT_SUPPORTED",
    "SSE smoke",
    "rollback",
    "envctl down",
    "gitleaks",
)

RUNBOOK_TERMS = (
    "SPEC-DOCKERHOST-RELEASE-RUNBOOK-001",
    "envctl check-project",
    "envctl validate-template",
    "--secret-env",
    "--secret-file",
    "/healthz",
    "/readyz",
    "STREAM_FALSE_NOT_SUPPORTED",
    "SSE Smoke",
    "回滚",
    "envctl down",
)

FORBIDDEN_TERMS = (
    "ENVCTL_TOKEN=",
    "OPENAI_API_KEY=sk-",
    "ZAI_API_KEY=sk-",
    "GEMINI_API_KEY=AIza",
    "-----BEGIN",
)


def main() -> int:
    failures: list[str] = []
    failures.extend(_missing_terms(CONTRACT, CONTRACT_TERMS))
    failures.extend(_missing_terms(RUNBOOK, RUNBOOK_TERMS))
    combined = "\n".join(_read(path) for path in (CONTRACT, RUNBOOK))
    for term in FORBIDDEN_TERMS:
        if term in combined:
            failures.append(f"forbidden secret-like marker present: {term}")
    if failures:
        for failure in failures:
            print(failure)
        return 1
    return 0


def _missing_terms(path: Path, terms: tuple[str, ...]) -> list[str]:
    text = _read(path)
    return [f"{path.relative_to(ROOT)} missing required term: {term}" for term in terms if term not in text]


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
