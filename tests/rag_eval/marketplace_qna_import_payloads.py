from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


EVAL_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVAL_DIR.parents[1]
DEFAULT_MANIFEST_PATH = EVAL_DIR / "marketplace_qna_rag_seed_manifest.json"


def build_document_payloads(
    *,
    knowledge_base_id: str,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
) -> list[dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    corpus_source = next(
        source for source in manifest["source_files"] if source["role"] == "corpus"
    )
    rows = [
        json.loads(line)
        for line in (REPO_ROOT / corpus_source["path"]).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    payloads: list[dict[str, Any]] = []
    for row in rows:
        meta = row.get("meta") or {}
        payloads.append(
            {
                "knowledge_base_id": knowledge_base_id,
                "title": meta.get("filename") or row["id"],
                "content": row["text"],
                "source_type": "api",
                "source_uri": meta["source_uri"],
                "mime_type": "text/markdown",
                "metadata": {
                    **meta,
                    "doc_id": row["id"],
                    "rag_seed_manifest_id": manifest["manifest_id"],
                    "coverage_contract_id": manifest["coverage_contract_id"],
                },
            }
        )
    return payloads


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate Marketplace QnA /rag/documents payloads as JSONL."
    )
    parser.add_argument("--knowledge-base-id", required=True)
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST_PATH))
    args = parser.parse_args()
    for payload in build_document_payloads(
        knowledge_base_id=args.knowledge_base_id,
        manifest_path=Path(args.manifest),
    ):
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
