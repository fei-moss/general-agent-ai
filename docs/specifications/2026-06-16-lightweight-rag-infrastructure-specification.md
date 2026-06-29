# 2026-06-16 Lightweight RAG Infrastructure Specification

> Boundary update: `SPEC-INTERNAL-RAG-BOUNDARY-001` supersedes the user-facing
> knowledge-base semantics in this phase-1 spec. `/rag/*` is now an internal
> management surface, and ordinary Chat requests consume only server-selected
> internal knowledge bases by default.

## Context

- Spec ID: `SPEC-RAG-INFRA-001`
- Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`
- Related architecture document: `docs/RAG_SOLUTION.md`
- Related runtime specs:
  - `SPEC-CHAT-RUNTIME-001`: realtime/batch Chat Server runtime boundary.
  - `SPEC-PROVIDER-GUARDRAILS-001`: provider/model quota and secret handling.
- PRD/source request:
  - Build a lightweight, self-owned RAG capability for the current Chat Server.
  - The system should not adopt a heavy RAG platform such as RAGFlow, Dify, or Flowise for the first phase.
  - Use DockerHost-derived PostgreSQL/Redis/pgvector environments for integration validation.
  - Keep Pydantic AI responsible only for Agent orchestration; RAG is exposed to the Agent as a tool.
- Target baseline:
  - `main` at or after `2feaa28 chore: add harness workflow gates`.
  - Existing RAG skeleton includes `app/rag/chunker.py`, `app/rag/embedder.py`, `app/rag/vector_store.py`, `app/rag/retriever.py`, and `search_knowledge` in `app/runtime/agent_factory.py`.
  - Existing `PgVectorStore` is a placeholder and is not enabled by the factory.
- Current behavior:
  - `HashEmbedder` and `InMemoryVectorStore` support deterministic local/demo retrieval.
  - `OpenAIEmbedder` supports OpenAI-compatible embedding APIs when explicitly configured.
  - `RAGRetriever.ingest()` can chunk, embed, and write to the in-memory store.
  - `RAGRetriever.retrieve()` can return in-memory hits with timeout/degradation semantics.
  - `search_knowledge` already exists as a Pydantic AI tool, but it is backed by the demo retriever adapter rather than a persistent knowledge store.
  - There is no persisted knowledge base, document, chunk, embedding, ingestion job, or retrieval log schema.
  - There is no RAG API surface, no pgvector-backed store, no ingestion worker, and no DockerHost adapter for pgvector validation.
- Problem:
  - The Agent can demonstrate retrieval, but cannot use durable project/private knowledge across processes or deployments.
  - The current in-memory vector store cannot support multi-worker, restart-safe, or audit-ready RAG.
  - Real RAG requires clear ownership, ingestion state, embedding configuration, query timeout/degradation, citation output, and retrieval logs.
- Non-goals:
  - No RAGFlow/Dify/Flowise platform integration in phase 1.
  - No GraphRAG, LightRAG, knowledge graph, or multi-hop graph retrieval in phase 1.
  - No full knowledge-base management UI in phase 1.
  - No broad connector ecosystem in phase 1.
  - No binary file upload/object storage/Docling parser requirement in phase 1.
  - No Qdrant/Milvus abstraction in phase 1.
  - No user billing, tenant quota marketplace, or external public knowledge sharing.

## Product Semantics

- User/operator workflow:
  - A user or operator creates a knowledge base.
  - A user imports Markdown/plain-text content into the knowledge base through an API.
  - The API validates ownership, writes a document record, creates an ingestion job, enqueues a RAG worker task, and returns `202`.
  - The worker parses text, chunks it, calls an embedder, writes chunks and embeddings to Postgres/pgvector, and marks the document embedded.
  - A Chat run may call `search_knowledge` during realtime or batch Agent execution.
  - A Chat run uses RAG only when the request metadata or run plan explicitly binds `knowledge_base_id`. If no knowledge base is bound, `search_knowledge` returns a degraded empty result with reason `no_knowledge_base`.
  - `search_knowledge` calls the RAG query service with the current user/run context and returns ranked chunks with citations.
  - The Agent answers based on retrieved content and cites retrieved sources when it uses them.
- State model:
  - Knowledge base status:
    - `ACTIVE`: can ingest and query.
    - `DISABLED`: cannot ingest or query; existing records remain for audit.
  - Document status:
    - `PENDING`: created, ingestion job not started.
    - `PARSING`: worker is normalizing/chunking content.
    - `EMBEDDING`: worker is calling embedding provider and preparing vectors.
    - `EMBEDDED`: chunks and embeddings are queryable.
    - `FAILED`: ingestion failed with sanitized error.
    - `DELETED`: soft-deleted or hidden from query; chunks must not be returned.
  - Ingestion job status:
    - `PENDING -> RUNNING -> SUCCEEDED|FAILED|CANCELLED`
  - Retrieval result status:
    - `degraded=false, chunks=[...]`: normal retrieval.
    - `degraded=false, chunks=[]`: no matching content.
    - `degraded=true`: timeout, dependency error, query embedder failure, pgvector error, or permission filter failure.
- Ownership and identity rules:
  - Phase 1 knowledge bases are user-owned via `owner_user_id`.
  - A user can only create, list, ingest into, query, or use a knowledge base they own.
  - A Chat run may only query knowledge bases owned by its `conversation.user_id`.
  - `agent_run_id`, `conversation_id`, and `user_id` must be passed into RAG query logging.
  - Team/RBAC scope is deferred; table design may leave room for `owner_type` later, but phase 1 behavior is user-owned only.
- Permissions/authentication:
  - All `/rag/*` APIs require the same user authentication boundary as Chat APIs.
  - Internal Agent tool calls must still enforce ownership; tool invocation is not a permission bypass.
  - Retrieval logs must not expose chunks from unauthorized knowledge bases.
- Empty, error, retry, timeout, duplicate, and partial-failure behavior:
  - Empty knowledge base name returns 422.
  - Empty document content returns 422.
  - Unknown knowledge base returns 404.
  - Knowledge base owner mismatch returns 403.
  - Querying a disabled knowledge base returns 409 or a degraded empty result when called from Agent context; external API should return a structured error.
  - Duplicate document content inside the same knowledge base should be idempotent by `(knowledge_base_id, content_hash)`:
    - same content and same title/source may return the existing document/job state.
    - same content with new metadata may either update metadata or create a new version; phase 1 chooses idempotent existing-document replay.
  - Ingestion failure marks `documents.status=FAILED` and `rag_ingestion_jobs.status=FAILED` with sanitized error.
  - Ingestion retries are allowed up to configured retry budget; retries must upsert chunks idempotently.
  - Query timeout returns `degraded=true` and does not fail the Chat run.
  - Query embedder/provider limit errors return `degraded=true` to the Agent unless the caller explicitly requested strict query API mode.
  - Agent final answer must not invent citations when no chunks are returned.
- Compatibility and migration expectations:
  - Existing demo behavior with `HashEmbedder + InMemoryVectorStore` must continue to work for local tests.
  - New persistent RAG must be opt-in through configuration, e.g. `RAG_VECTOR_STORE=pgvector`.
  - Existing Chat `search_knowledge` tool name remains stable.
  - Existing runtime event types do not change.
  - Existing `tool_call_log` remains the tool-call audit table; `rag_retrieval_logs` stores retrieval-specific diagnostics.

## API / Interface Contract

- Routes, commands, events, jobs, or UI surfaces:
  - `POST /rag/knowledge-bases`
  - `GET /rag/knowledge-bases`
  - `GET /rag/knowledge-bases/{knowledge_base_id}`
  - `POST /rag/documents`
  - `GET /rag/documents/{document_id}`
  - `GET /rag/ingestion-jobs/{job_id}`
  - `POST /rag/query`
  - Celery task: `app.tasks.agent_tasks.rag_ingest_document`
  - Internal service: `RAGQueryService.query(...)`
  - Agent tool: existing `search_knowledge`
- `POST /rag/knowledge-bases` request:
  - `name: str` required, 1-128 chars.
  - `description: str | None`, max 1024 chars.
- `POST /rag/knowledge-bases` response:
  - `id: str`
  - `owner_user_id: str`
  - `name: str`
  - `description: str | None`
  - `status: ACTIVE`
  - `created_at: datetime`
  - `updated_at: datetime`
- `POST /rag/documents` request:
  - `knowledge_base_id: str` required.
  - `title: str | None`, max 512 chars.
  - `content: str` required, non-empty.
  - `source_type: manual|api|upload|url`, phase 1 accepts `manual|api`; `upload|url` are reserved.
  - `source_uri: str | None`, max 2048 chars.
  - `mime_type: str | None`; phase 1 accepts text-like values only.
  - `metadata: dict[str, Any]`, max serialized size configured.
- `POST /rag/documents` response:
  - `document_id: str`
  - `job_id: str`
  - `status: PENDING|EMBEDDED|FAILED`
  - `replayed: bool` indicates content-hash idempotency replay.
- `POST /rag/query` request:
  - `knowledge_base_id: str` required.
  - `query: str` required, non-empty.
  - `top_k: int | None`, default `RAG_DEFAULT_TOP_K`, hard max `RAG_MAX_TOP_K`.
  - `filters: dict[str, Any] | None`, phase 1 supports safe metadata equality filters only.
  - `strict: bool = false`; strict mode returns errors instead of degraded results for internal testing/admin debugging.
- `POST /rag/query` response:
  - `chunks: list[KnowledgeSearchResult]`
  - `degraded: bool`
  - `reason: str | None`
  - `latency_ms: int`
  - `query_id: str | None`
- `KnowledgeSearchResult`:
  - `chunk_id: str`
  - `document_id: str`
  - `knowledge_base_id: str`
  - `title: str | None`
  - `content: str`
  - `score: float`
  - `citation: object`
    - `source_uri: str | None`
    - `page: int | None`
    - `section: str | None`
    - `chunk_index: int`
  - `metadata: dict[str, Any]`
- Status/error codes:
  - 200: query/list/status read success.
  - 202: document accepted for ingestion.
  - 401: unauthenticated.
  - 403: owner mismatch.
  - 404: knowledge base/document/job not found.
  - 409: disabled knowledge base, duplicate conflict that cannot be replayed, or incompatible index version.
  - 422: validation failure.
  - 429: embedding provider limit when strict API mode is used.
  - 503: pgvector unavailable, queue unavailable, or embedder unavailable in strict mode.
- Pagination/sorting/filtering:
  - Knowledge base and document list endpoints must support `limit` and `cursor` or `offset` before broad use; phase 1 may keep list endpoints small and internal.
  - `POST /rag/query` sorts by descending similarity score after applying filters.
  - Metadata filters must be allowlisted; arbitrary raw SQL/JSON path fragments are forbidden.
- Backward compatibility:
  - Existing `search_knowledge(query)` tool call remains valid.
  - The adapter keeps `knowledge_base_id` out of the LLM-facing tool schema in phase 1. The server resolves it from request metadata/run plan; if absent, the tool returns a degraded empty result rather than guessing.
  - Tool return shape can include more fields, but must retain text content under a stable field consumable by current mock and prompt logic.

## Data / Schema / Projection Impact

- Tables, indexes, migrations, backfills:
  - Enable pgvector:
    - `CREATE EXTENSION IF NOT EXISTS vector;`
  - Add `knowledge_base`:
    - `id VARCHAR(64) PRIMARY KEY`
    - `owner_user_id VARCHAR(64) NOT NULL`
    - `name VARCHAR(128) NOT NULL`
    - `description TEXT`
    - `status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE'`
    - `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
    - `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`
    - index `(owner_user_id, status)`
  - Add `rag_document`:
    - `id VARCHAR(64) PRIMARY KEY`
    - `knowledge_base_id VARCHAR(64) NOT NULL REFERENCES knowledge_base(id) ON DELETE CASCADE`
    - `owner_user_id VARCHAR(64) NOT NULL`
    - `title VARCHAR(512)`
    - `source_type VARCHAR(32) NOT NULL`
    - `source_uri TEXT`
    - `mime_type VARCHAR(128)`
    - `content_hash VARCHAR(128) NOT NULL`
    - `raw_content TEXT` phase 1 may store text content in DB; if later files/object storage are added, replace with object pointer.
    - `status VARCHAR(16) NOT NULL DEFAULT 'PENDING'`
    - `error_message TEXT`
    - `metadata JSONB NOT NULL DEFAULT '{}'::jsonb`
    - `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
    - `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`
    - unique `(knowledge_base_id, content_hash)`
    - indexes `(knowledge_base_id, status)`, `(owner_user_id, created_at)`
  - Add `rag_document_chunk`:
    - `id VARCHAR(64) PRIMARY KEY`
    - `document_id VARCHAR(64) NOT NULL REFERENCES rag_document(id) ON DELETE CASCADE`
    - `knowledge_base_id VARCHAR(64) NOT NULL REFERENCES knowledge_base(id) ON DELETE CASCADE`
    - `owner_user_id VARCHAR(64) NOT NULL`
    - `chunk_index INTEGER NOT NULL`
    - `content TEXT NOT NULL`
    - `content_hash VARCHAR(128) NOT NULL`
    - `token_count INTEGER NOT NULL DEFAULT 0`
    - `page_number INTEGER`
    - `section_title TEXT`
    - `metadata JSONB NOT NULL DEFAULT '{}'::jsonb`
    - `embedding vector(RAG_EMBEDDING_DIM) NOT NULL`
    - `embedding_provider VARCHAR(64) NOT NULL`
    - `embedding_model VARCHAR(128) NOT NULL`
    - `embedding_dim INTEGER NOT NULL`
    - `index_version VARCHAR(64) NOT NULL`
    - `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
    - unique `(document_id, index_version, chunk_index)`
    - indexes `(knowledge_base_id, index_version)`, `(document_id)`, `GIN(metadata)`
    - pgvector HNSW or IVFFlat index on `embedding` for production-like testing.
  - Add `rag_ingestion_job`:
    - `id VARCHAR(64) PRIMARY KEY`
    - `document_id VARCHAR(64) NOT NULL REFERENCES rag_document(id) ON DELETE CASCADE`
    - `knowledge_base_id VARCHAR(64) NOT NULL`
    - `owner_user_id VARCHAR(64) NOT NULL`
    - `status VARCHAR(16) NOT NULL DEFAULT 'PENDING'`
    - `attempts INTEGER NOT NULL DEFAULT 0`
    - `payload JSONB`
    - `error_message TEXT`
    - `started_at TIMESTAMPTZ`
    - `finished_at TIMESTAMPTZ`
    - `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
    - index `(status, created_at)`
  - Add `rag_retrieval_log`:
    - `id VARCHAR(64) PRIMARY KEY`
    - `agent_run_id VARCHAR(64)`
    - `conversation_id VARCHAR(64)`
    - `user_id VARCHAR(64) NOT NULL`
    - `knowledge_base_id VARCHAR(64) NOT NULL`
    - `query_hash VARCHAR(128) NOT NULL`
    - `query_preview TEXT`
    - `top_k INTEGER NOT NULL`
    - `matched_chunk_ids JSONB NOT NULL DEFAULT '[]'::jsonb`
    - `scores JSONB NOT NULL DEFAULT '[]'::jsonb`
    - `latency_ms INTEGER NOT NULL`
    - `degraded BOOLEAN NOT NULL DEFAULT false`
    - `reason VARCHAR(64)`
    - `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
    - indexes `(agent_run_id)`, `(conversation_id)`, `(knowledge_base_id, created_at)`
- Read models, projections, snapshots, caches:
  - RAG query result cache may be added only after correctness is proven; phase 1 can rely on direct pgvector queries.
  - If a cache is added, cache keys must include `user_id`, `knowledge_base_id`, `index_version`, query hash, `top_k`, and filter hash.
  - Redis is not authoritative storage for documents or chunks.
- Rebuild or cleanup operators:
  - Reingestion for one document deletes/replaces chunks for `(document_id, index_version)` in one short transaction after embeddings are prepared.
  - Full reindex creates a new `index_version`, writes new chunks, then atomically marks the knowledge base active index version; phase 1 may defer full reindex API but must not make it impossible.
  - Deleting a document must make its chunks non-queryable.
- Historical data behavior:
  - Existing in-memory demo documents are not migrated.
  - Existing Chat runs have no retrieval logs; no backfill.
- Performance-sensitive queries or write paths:
  - Ingestion must not hold DB connections while calling embedding providers.
  - Query path must not hold DB connections while calling query embedding provider.
  - pgvector search should be one bounded query over a single knowledge base and index version.
  - Retrieval logs should be written after query result assembly, not inside the vector search transaction.
  - Online RAG query timeout target is configurable and defaults to 1500ms for Agent tool calls.

## Architecture

- Modules/files expected to change:
  - `app/core/config.py`: RAG/embedding settings.
  - `app/core/models.py`: RAG ORM models.
  - `app/core/schemas.py`: RAG API schemas.
  - `app/core/interfaces.py`: vector store/search result interface expansion if needed.
  - `app/db/init.sql`: pgvector extension and RAG tables/indexes.
  - `app/db/repositories.py`: knowledge base, document, ingestion job, chunk, retrieval log repositories.
  - `app/rag/vector_store.py`: real `PgVectorStore`.
  - `app/rag/embedder.py`: embedding provider decoupled from chat `llm_provider`.
  - `app/rag/retriever.py`: persistent retriever/query service integration.
  - new `app/rag/parser.py`: phase 1 text/markdown parser.
  - new `app/rag/service.py`: ingestion and query application service.
  - new `app/api/routers/rag.py`: RAG API.
  - `app/runtime/adapters.py`: `RetrieverAdapter` passes user/run context and maps citations.
  - `app/runtime/deps.py`: RAG query service injection.
  - `app/runtime/agent_factory.py`: prompt/tool return guidance for citations.
  - `app/tasks/agent_tasks.py`: RAG ingestion task.
  - `app/tasks/celery_app.py`: route ingestion task to `q.rag`.
  - `dockerhost/`: pgvector-capable integration environment adapter.
  - tests under `tests/`.
- Data flow:
  - Ingestion:
    1. API authenticates user.
    2. API validates knowledge base ownership.
    3. API computes content hash.
    4. API replays existing document/job if `(knowledge_base_id, content_hash)` already exists.
    5. API writes document and ingestion job in one transaction.
    6. API enqueues `rag_ingest_document(job_id, document_id)`.
    7. Worker loads raw content in a short transaction and releases DB connection.
    8. Worker parses and chunks content in memory.
    9. Worker calls embedding provider in batches without DB connection.
    10. Worker reopens DB transaction and upserts chunks/embeddings.
    11. Worker marks job/document succeeded or failed.
  - Query:
    1. Agent or API passes user id, knowledge base id, query, filters, and top_k.
    2. Service validates knowledge base ownership/status.
    3. Service calls query embedder without holding DB transaction.
    4. Service runs pgvector search with owner/kb/index/version filters.
    5. Service applies threshold/context trimming.
    6. Service writes retrieval log.
    7. Service returns chunks with citation objects.
  - Agent:
    1. Pydantic AI decides whether to call `search_knowledge`.
    2. Tool resolves knowledge base from server-side run metadata.
    3. Tool receives `KnowledgeSearchResult[]`.
    4. Agent composes answer and cites retrieved chunks.
- Transaction/concurrency boundaries:
  - No DB connection is held across embedding provider calls.
  - No DB connection is held across LLM streaming.
  - Ingestion job state updates are idempotent.
  - Chunk upsert for a document/index version is atomic.
  - Query reads are bounded and scoped by owner/kb/index version.
  - Embedding provider quota uses the existing provider limiter path or an extension of it; it is not enforced through Postgres.
  - Realtime `search_knowledge` must have short timeout/degraded fallback.
  - Long RAG, reindexing, and document parsing beyond plain text go through worker/batch path.
- Embedding provider contract:
  - `embedding_provider=hash` remains the zero-secret local/test default.
  - Explicit real providers must not silently fall back to `hash` when their secret is missing.
  - `embedding_provider=openai` uses an OpenAI-compatible `/embeddings` endpoint with bearer auth.
  - `embedding_provider=gemini` uses the Gemini API `models/{model}:batchEmbedContents` endpoint with `x-goog-api-key` auth.
  - Gemini model names may be configured as either `gemini-embedding-2` or `models/gemini-embedding-2`; requests normalize to `models/{model}`.
  - Gemini batch requests must preserve one output vector per input text and preserve input order.
  - Gemini requests should set `output_dimensionality` from `embedding_dim` so pgvector dimensions, response vectors, and stored metadata stay aligned.
  - `embedding_api_key` is the provider-neutral secret; Gemini may also read `gemini_api_key` for operator convenience. Neither value may be logged, persisted, or committed.
- Observability/logging/metrics:
  - Metrics:
    - `rag_ingestion_jobs_total{status}`
    - `rag_ingestion_duration_seconds`
    - `rag_ingestion_failures_total{reason}`
    - `rag_chunks_total{knowledge_base_id,index_version}` or low-cardinality equivalent if labels are constrained.
    - `rag_embedding_requests_total{provider,model,status}`
    - `rag_embedding_request_seconds{provider,model}`
    - `rag_query_seconds{degraded,reason}`
    - `rag_query_degraded_total{reason}`
    - `rag_query_empty_result_total`
    - `rag_retrieved_chunks`
  - Logs include document_id, knowledge_base_id, job_id, agent_run_id, top_k, latency_ms, degraded reason, and matched chunk ids.
  - Logs must not print full sensitive document content, full query text by default, provider secrets, or raw embeddings.
  - Retrieval log stores query hash and optional short sanitized preview; full query storage is not required in phase 1.
- Rollback strategy:
  - Disable persistent RAG with `RAG_ENABLED=false` or `RAG_VECTOR_STORE=memory`.
  - Keep existing in-memory mock retrieval for local Chat tests.
  - Disable `/rag/*` router if migration is not applied.
  - If pgvector query latency is unacceptable, route Agent calls to degraded empty results while keeping Chat runtime healthy.
  - Schema rollback requires dropping RAG tables only if no production knowledge content must be preserved; otherwise leave tables unused.

## Harness Classification

- Expected gate(s):
  - `HARNESS-SPEC-FIRST-FEATURE`
  - `ai_boundaries`
  - `spec_contract`
  - `harness_workflows`
  - focused RAG unit/integration tests
  - full `pytest`
  - release verification
- Performance-sensitive class:
  - Online query path is performance-sensitive for TTFT and Agent tool latency.
  - Ingestion path is throughput-sensitive but not realtime-sensitive.
  - pgvector search, embedding batch calls, and DB pool checkout must be measured before production use.
- Whether harness mapping must be extended:
  - No new workflow class is required.
  - Add focused RAG tests and, if DockerHost adapter is implemented, optional DockerHost pgvector smoke evidence.
- Required performance evidence:
  - Local unit tests prove degraded fallback and no DB connection across embedding calls via fakes/hooks.
  - DockerHost pgvector smoke proves `CREATE EXTENSION vector`, schema creation, ingest, and query.
  - Query p95 target for small knowledge base: `/rag/query` p95 < 300ms excluding embedding provider network variance.
  - Agent RAG tool p95 target: < 1500ms including query embedding under configured provider.
- Focused verification commands:
  - `.venv/bin/python -m pytest tests/test_rag_*.py -q`
  - `.venv/bin/python -m pytest tests/test_vector_store.py -q`
  - `.venv/bin/python -m pytest tests/test_agent_factory.py tests/test_orchestrator.py -q`
  - `bash scripts/check_spec_contract.sh`
  - `bash scripts/check_harness_workflows.sh`
- Prerelease-grade verification commands:
  - `git diff --check`
  - `.venv/bin/python -m pytest -q`
  - `AI_BOUNDARY_APPROVED=1 make verify-release`
  - DockerHost pgvector smoke after adapter exists:
    - `source /Users/chris/.codex-local/dockerhost/envctl_env.sh`
    - `envctl up --name <owner>-general-agent-ai-rag --git-url git@github.com:fei-moss/general-agent-ai.git --git-ref <branch-or-sha> --git-subdir dockerhost`
    - `envctl status --name <owner>-general-agent-ai-rag`
    - run project smoke command inside API/worker container or through exposed API.

## Acceptance Criteria

- Functional:
  - `SPEC-RAG-INFRA-001`: user can create a knowledge base.
  - `SPEC-RAG-INFRA-001`: user can import Markdown/plain text by API and receive `document_id` and `job_id`.
  - `SPEC-RAG-INFRA-001`: worker ingests text into persisted chunks and pgvector embeddings.
  - `SPEC-RAG-INFRA-001`: `/rag/query` returns ranked chunks with `chunk_id`, `document_id`, `score`, `content`, and citation.
  - `SPEC-RAG-INFRA-001`: `search_knowledge` uses persistent RAG when enabled and still supports deterministic mock/local behavior when disabled.
  - `SPEC-RAG-INFRA-001`: Agent answers can reference returned citation source ids and do not invent citations.
  - `SPEC-RAG-INFRA-001`: `embedding_provider=gemini` sends batch requests to Gemini Embedding 2, parses `embeddings[].values`, and never exposes the API key.
- Edge cases:
  - Empty content returns 422.
  - Unknown/unauthorized knowledge base returns 404/403.
  - Disabled knowledge base does not return chunks.
  - Duplicate content replays existing document/job state.
  - Ingestion retry does not duplicate chunks.
  - Query timeout returns degraded result and does not fail Chat run.
  - Embedding dimension mismatch fails ingestion before chunks become queryable.
  - pgvector unavailable returns degraded result for Agent tool and strict error for strict API mode.
- Compatibility:
  - Existing `HashEmbedder` and `InMemoryVectorStore` tests continue to pass.
  - Existing Chat runtime tests continue to pass.
  - Existing `TOKEN` events, `ChatAccepted` envelope, and Agent run state machine are unchanged.
  - `tool_call_log` still records `search_knowledge` tool invocation; `rag_retrieval_logs` adds retrieval diagnostics.
- Operational:
  - DockerHost adapter can run a pgvector-enabled Postgres stack.
  - No provider secrets or DockerHost token are committed.
  - Ingestion and query metrics/logs are available.
  - RAG can be disabled by config without disabling Chat.
  - Postgres/pgvector volume uses DockerHost managed volume with quota.
- Evidence artifacts:
  - `.artifacts/release/spec_contract.json`
  - `.artifacts/release/harness_workflows.json`
  - `.artifacts/release/summary.json`
  - Optional `.artifacts/release/rag_pgvector_smoke.json` after DockerHost smoke exists.

## Review Notes

- Open questions:
  - None blocking for phase 1. Provider/model, object storage, and default knowledge-base selection are intentionally constrained by the accepted assumptions below.
- Accepted assumptions:
  - Phase 1 is user-owned knowledge bases only; no team/RBAC.
  - Phase 1 supports JSON text/Markdown import only; binary upload and Docling are deferred.
  - Phase 1 stores imported text content in Postgres `rag_document.raw_content`; object storage is deferred until binary upload/file retention is introduced.
  - Local/test default embedding provider is deterministic `hash`; production must explicitly configure `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`, dimension, and secret source before enabling persistent RAG with a real provider.
  - Gemini Embedding 2 is the preferred first production semantic embedding option for this project. Its key is injected from local/secret-manager environment, not repository files.
  - Agent RAG uses only an explicitly bound `knowledge_base_id` from request metadata/run plan. It does not silently choose the first active user knowledge base.
  - pgvector is sufficient for the expected initial scale.
  - DockerHost is the preferred integration environment for pgvector validation.
  - In-memory RAG remains available for local deterministic tests.
- Rejected alternatives:
  - Full RAG platform adoption is rejected for phase 1 because it overlaps with existing Chat runtime responsibilities.
  - GraphRAG is rejected for phase 1 because it adds indexing and reasoning complexity before baseline retrieval quality is proven.
  - Qdrant/Milvus are deferred until pgvector capacity or query-latency evidence says they are needed.
- Reviewer findings and resolution:
  - Pending. Implementation plan must be reviewed against this specification before code changes.
