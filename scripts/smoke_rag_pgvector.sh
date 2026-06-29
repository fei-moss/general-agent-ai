#!/usr/bin/env bash
set -euo pipefail

API_BASE_URL="${API_BASE_URL:-}"
SMOKE_USER="${SMOKE_USER:-rag-smoke-user}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if [[ -z "${API_BASE_URL}" ]]; then
  echo "API_BASE_URL is required, for example: https://api-<env>.<domain>" >&2
  exit 2
fi

"${PYTHON_BIN}" - <<'PY'
import json
import os
import sys
import time
import urllib.error
import urllib.request

base = os.environ["API_BASE_URL"].rstrip("/")
user = os.environ.get("SMOKE_USER", "rag-smoke-user")
headers = {
    "Content-Type": "application/json",
    "X-API-Key": user,
}


def request(method, path, payload=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{base}{path}",
        data=data,
        method=method,
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body or "{}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        raise RuntimeError(f"{method} {path} failed {exc.code}: {body}") from exc


evidence = {"api_base_url": base, "user": user}
status, health = request("GET", "/healthz")
evidence["healthz"] = {"status_code": status, "body": health}

_, kb = request(
    "POST",
    "/rag/knowledge-bases",
    {"name": f"rag-smoke-{int(time.time())}", "description": "pgvector smoke"},
)
kb_id = kb["id"]
evidence["knowledge_base_id"] = kb_id

_, accepted = request(
    "POST",
    "/rag/documents",
    {
        "knowledge_base_id": kb_id,
        "title": "DockerHost RAG smoke",
        "content": "DockerHost RAG smoke document. pgvector stores chunks and hash embeddings for retrieval.",
        "source_type": "manual",
        "source_uri": "smoke://dockerhost-rag",
        "mime_type": "text/plain",
        "metadata": {"section": "smoke"},
    },
)
evidence["document_id"] = accepted["document_id"]
evidence["job_id"] = accepted["job_id"]

deadline = time.time() + 60
job = None
while time.time() < deadline:
    _, job = request("GET", f"/rag/ingestion-jobs/{accepted['job_id']}")
    if job["status"] in {"SUCCEEDED", "FAILED", "CANCELLED"}:
        break
    time.sleep(2)

evidence["job"] = job
if not job or job["status"] != "SUCCEEDED":
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    sys.exit(1)

_, query = request(
    "POST",
    "/rag/query",
    {
        "knowledge_base_id": kb_id,
        "query": "Where does pgvector store the chunks?",
        "top_k": 3,
        "strict": True,
    },
)
evidence["query"] = query
if query.get("degraded") or not query.get("chunks"):
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    sys.exit(1)

os.makedirs(".artifacts/release", exist_ok=True)
with open(".artifacts/release/rag_pgvector_smoke.json", "w", encoding="utf-8") as fh:
    json.dump(evidence, fh, ensure_ascii=False, indent=2)
print(json.dumps(evidence, ensure_ascii=False, indent=2))
PY
