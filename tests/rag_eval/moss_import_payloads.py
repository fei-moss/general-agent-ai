from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


EVAL_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVAL_DIR.parents[1]
DEFAULT_MANIFEST_PATH = EVAL_DIR / "moss_rag_seed_manifest.json"


def build_document_payloads(
    *,
    knowledge_base_id: str,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
) -> list[dict[str, Any]]:
    """Build deterministic `/rag/documents` request bodies from the MOSS seed."""
    manifest = _load_json(manifest_path)
    corpus_source = _source_by_role(manifest, "corpus")
    rows = _load_jsonl(REPO_ROOT / corpus_source["path"])
    return [_build_payload(row, manifest, knowledge_base_id) for row in rows]


def _build_payload(
    row: dict[str, Any],
    manifest: dict[str, Any],
    knowledge_base_id: str,
) -> dict[str, Any]:
    meta = row.get("meta") or {}
    source = str(meta.get("source") or "moss")
    section = str(meta.get("section") or row["id"])
    metadata = {
        **meta,
        "doc_id": row["id"],
        "rag_seed_manifest_id": manifest["manifest_id"],
        "coverage_contract_id": manifest["coverage_contract_id"],
    }
    return {
        "knowledge_base_id": knowledge_base_id,
        "title": f"{source}/{section}",
        "content": row["text"],
        "source_type": "api",
        "source_uri": meta.get("source_url"),
        "mime_type": "text/plain",
        "metadata": metadata,
    }


def _source_by_role(manifest: dict[str, Any], role: str) -> dict[str, Any]:
    for source in manifest["source_files"]:
        if source["role"] == role:
            return source
    raise ValueError(f"missing source role: {role}")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate reviewed MOSS Wiki /rag/documents payloads as JSONL."
    )
    parser.add_argument("--knowledge-base-id", required=True)
    parser.add_argument(
        "--manifest",
        default=str(DEFAULT_MANIFEST_PATH),
        help="Path to moss_rag_seed_manifest.json",
    )
    args = parser.parse_args()
    for payload in build_document_payloads(
        knowledge_base_id=args.knowledge_base_id,
        manifest_path=Path(args.manifest),
    ):
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
