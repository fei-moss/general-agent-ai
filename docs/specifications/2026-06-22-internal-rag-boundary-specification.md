# 2026-06-22 Internal RAG Boundary Specification

## Context

- Spec ID: `SPEC-INTERNAL-RAG-BOUNDARY-001`
- Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`
- Supersedes part of: `SPEC-RAG-INFRA-001`
- Related implementation plan: `docs/implementation-plans/2026-06-22-internal-rag-boundary-implementation-plan.md`
- Source request:
  - RAG is not a user-facing product feature.
  - RAG exists so internal operators can upload first-party documents into an internal knowledge base.
  - Ordinary Chat users should not create, list, query, or select RAG knowledge bases.
  - Ordinary Chat may still benefit from RAG because the server can retrieve internal documents during an Agent run.

## Problem

The current phase-1 RAG API lets any authenticated `CurrentUser` create knowledge bases, upload documents, directly query `/rag/query`, and pass `metadata.knowledge_base_id` in a Chat request. That makes RAG look like a user-owned public capability.

That is the wrong product boundary for the first official Chat Server release. RAG should be an internal knowledge-management plane plus a hidden retrieval enhancement for normal Chat.

## Product Semantics

- `/chat` remains the external integration surface for ordinary users and upstream systems.
- `/rag/*` is an internal management surface for trusted operators or ingestion agents only.
- Ordinary users must not be asked to pass `knowledge_base_id` in Chat metadata.
- Chat runtime must ignore client-provided `metadata.knowledge_base_id` by default.
- Chat runtime may bind an internal knowledge base only from server-side configuration.
- Internal knowledge bases can be owned by a stable internal owner id, separate from the real user asking the question.
- RAG retrieval logs must retain the real requesting `user_id`, `conversation_id`, and `agent_run_id`.
- RAG query authorization must not use the real chat user as the knowledge-base owner when the server has selected an internal knowledge base.

## Configuration Contract

- `RAG_ADMIN_USER_IDS`
  - Comma-separated internal identities allowed to call `/rag/*`.
  - Empty value means `/rag/*` fails closed with `403 RAG_ADMIN_FORBIDDEN`.
- `RAG_DEFAULT_KNOWLEDGE_BASE_ID`
  - Optional server-side knowledge base id used by ordinary Chat runs.
  - If empty, Chat runs have no bound RAG knowledge base unless debug override is enabled.
- `RAG_INTERNAL_OWNER_USER_ID`
  - Optional owner id for the server-selected internal knowledge base.
  - If set, the query service checks this owner when retrieving the internal KB while logging the real requester.
- `RAG_ALLOW_CLIENT_KNOWLEDGE_BASE_ID`
  - Boolean escape hatch for local/debug compatibility.
  - Defaults to `false`.
  - Must not be enabled in production unless there is a separate authorization layer.

## API Contract

- All `/rag/*` routes require the caller identity to be present in `RAG_ADMIN_USER_IDS`.
- Non-admin callers receive:
  - status: `403`
  - detail: `RAG_ADMIN_FORBIDDEN`
- Existing route paths remain available for internal operators:
  - `POST /rag/knowledge-bases`
  - `GET /rag/knowledge-bases`
  - `GET /rag/knowledge-bases/{knowledge_base_id}`
  - `POST /rag/documents`
  - `GET /rag/documents/{document_id}`
  - `GET /rag/ingestion-jobs/{job_id}`
  - `POST /rag/query`
- Existing request and response schemas remain compatible for internal callers.

## Chat Runtime Contract

- Default selection order:
  1. If `RAG_DEFAULT_KNOWLEDGE_BASE_ID` is set, use it.
  2. Else if `RAG_ALLOW_CLIENT_KNOWLEDGE_BASE_ID=true`, accept `metadata.knowledge_base_id`.
  3. Else no knowledge base is bound.
- The run plan may record the selected server-side `knowledge_base_id`.
- The run plan must not treat user-provided metadata as authoritative when client KB selection is disabled.
- When `RAG_INTERNAL_OWNER_USER_ID` is set, the RAG query service uses it for knowledge-base ownership checks and vector-store owner filtering.
- Retrieval logs still store the real `user_id`.

## Security And Privacy Requirements

- No provider secrets, embedding keys, tokens, or private credentials may be stored in docs, tests, code, events, or logs.
- `/rag/query` is internal because it can expose raw chunks from internal documents.
- Normal Chat responses may use internal RAG content only through the Agent answer path.
- The LLM-facing `search_knowledge` tool schema must not expose `knowledge_base_id` as a user-selectable argument.

## Acceptance Criteria

- Non-admin requests to `/rag/*` return `403 RAG_ADMIN_FORBIDDEN` before repository access.
- Admin requests to `/rag/*` continue to reach the existing repository/service flow.
- Chat plan selection ignores `metadata.knowledge_base_id` by default.
- Chat plan selection uses `RAG_DEFAULT_KNOWLEDGE_BASE_ID` when configured.
- Chat retrieval passes configured internal owner id to `RAGQueryService`.
- `RAGQueryService` can query a KB owned by `owner_user_id` while logging the real requester.
- The integration guide describes `/rag/*` as internal-only and removes normal-user `knowledge_base_id` instructions.
- Focused tests and `make verify-release` pass.
