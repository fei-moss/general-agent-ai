# 2026-06-16 Lightweight RAG Infrastructure Implementation Plan

## Plan Header

- Specification: `docs/specifications/2026-06-16-lightweight-rag-infrastructure-specification.md`
- Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`
- Target branch/baseline: `main` at or after `2feaa28 chore: add harness workflow gates`.
- Scope summary: Implement phase-1 lightweight RAG infrastructure: persisted user-owned knowledge bases, text/Markdown ingestion, pgvector-backed chunks/embeddings, RAG query service, retrieval logs, Agent `search_knowledge` integration, DockerHost pgvector adapter, and focused verification.
- Out of scope:
  - RAGFlow/Dify/Flowise integration.
  - GraphRAG/LightRAG.
  - Qdrant/Milvus.
  - Binary file upload, object storage, Docling, OCR, or office document parsing.
  - Team/RBAC knowledge bases.
  - Full UI for knowledge base management.
  - Broad embedding provider marketplace beyond OpenAI-compatible and Gemini hooks.

## Change Steps

### Step 1: Add RAG Test Harness And Fakes First

- Files/modules:
  - `tests/harness_fakes.py`
  - new `tests/test_rag_api.py`
  - new `tests/test_rag_service.py`
  - new `tests/test_rag_pgvector_store.py`
  - new `tests/test_rag_agent_tool.py`
  - update `tests/test_vector_store.py`
- Behavior change:
  - Define test fakes for embedder, vector store, short-lived DB session hooks, queue enqueue, and RAG query timeout.
  - Encode phase-1 acceptance before implementation:
    - create knowledge base;
    - import text document;
    - duplicate content replay;
    - ingestion creates chunks and embeddings;
    - query returns citations;
    - query timeout degrades without failing Chat;
    - no knowledge base bound returns `no_knowledge_base`;
    - dimension mismatch fails ingestion before chunks are queryable.
- Data contract impact:
  - Tests become the executable contract for `SPEC-RAG-INFRA-001`.
- Tests to add/update:
  - New focused RAG test files above.
- Verification command:
  - `.venv/bin/python -m pytest tests/test_rag_*.py tests/test_vector_store.py -q`
- Rollback or compatibility note:
  - Test files can be removed without runtime impact if the feature is abandoned before implementation.

### Step 2: Add RAG Configuration And Schemas

- Files/modules:
  - `app/core/config.py`
  - `app/core/schemas.py`
  - optionally `app/core/enums.py` if status enums are centralized.
- Behavior change:
  - Add config:
    - `rag_enabled: bool = true`
    - `rag_vector_store: str = "memory"`
    - `rag_default_top_k: int = 5`
    - `rag_max_top_k: int = 10`
    - `rag_query_timeout_ms: int = 1500`
    - `rag_score_threshold: float = 0.0`
    - `rag_max_context_chars: int = 6000`
    - `rag_chunk_size: int`
    - `rag_chunk_overlap: int`
    - `rag_index_version: str = "v1"`
    - `embedding_provider: str = "hash"` (`hash|openai|gemini`)
    - `embedding_model: str = "hash"`
    - `embedding_dim: int`
    - `embedding_batch_size: int = 64`
    - `embedding_timeout_s: float = 30`
    - optional `embedding_api_key_file/base_url`.
  - Add Pydantic schemas for knowledge base, document import/status, ingestion job, query request/response, and `KnowledgeSearchResult`.
- Data contract impact:
  - Public/internal API request/response types become stable.
- Tests to add/update:
  - Schema validation tests for empty names/content, top_k bounds, source_type constraints, and metadata shape.
- Verification command:
  - `.venv/bin/python -m pytest tests/test_rag_api.py -q`
- Rollback or compatibility note:
  - Defaults keep existing in-memory RAG and local tests working.

### Step 3: Add RAG ORM Models And SQL Schema

- Files/modules:
  - `app/core/models.py`
  - `app/db/init.sql`
  - new or updated DB test fixtures.
- Behavior change:
  - Add ORM models and SQL DDL for:
    - `knowledge_base`
    - `rag_document`
    - `rag_document_chunk`
    - `rag_ingestion_job`
    - `rag_retrieval_log`
  - Enable pgvector in `init.sql` with `CREATE EXTENSION IF NOT EXISTS vector;`.
  - Use `vector(<embedding_dim>)` for Postgres integration. Keep local SQLite/unit paths from importing pgvector-only SQL unless explicitly using Postgres.
- Data contract impact:
  - New persisted data model and indexes.
  - `rag_document.raw_content` stores phase-1 imported text.
- Tests to add/update:
  - Repository/schema tests for table creation, uniqueness, owner filters, status updates, and retrieval log writes.
  - Postgres-only integration test guarded/skipped when pgvector is unavailable.
- Verification command:
  - `.venv/bin/python -m pytest tests/test_db_repositories.py tests/test_rag_pgvector_store.py -q`
- Rollback or compatibility note:
  - New tables are additive. Disabling `rag_enabled` keeps Chat runtime independent.

### Step 4: Implement Repositories

- Files/modules:
  - `app/db/repositories.py`
  - possibly new `app/db/rag_repositories.py` if the existing file becomes too broad.
- Behavior change:
  - Add repositories:
    - `KnowledgeBaseRepository`
    - `RAGDocumentRepository`
    - `RAGIngestionJobRepository`
    - `RAGChunkRepository`
    - `RAGRetrievalLogRepository`
  - Enforce owner-scoped reads.
  - Implement content-hash replay for `(knowledge_base_id, content_hash)`.
  - Implement idempotent document/index-version chunk replacement.
- Data contract impact:
  - Repository layer becomes the only DB write path for RAG service.
- Tests to add/update:
  - Unit tests with short session scopes proving no long-held DB session across embedding calls via service-level hooks.
- Verification command:
  - `.venv/bin/python -m pytest tests/test_rag_service.py tests/test_db_repositories.py -q`
- Rollback or compatibility note:
  - Additive repositories do not alter existing Chat repositories.

### Step 5: Implement Parser, Chunking Config, And Embedding Provider Separation

- Files/modules:
  - new `app/rag/parser.py`
  - `app/rag/chunker.py`
  - `app/rag/embedder.py`
  - `app/core/secrets.py` if embedding secret names need mapping.
  - `app/runtime/provider_limits.py` if embedding admission uses existing provider limiter.
- Behavior change:
  - Add `PlainTextParser` and `MarkdownParser` for text-like documents.
  - Let chunk size/overlap come from settings.
  - Decouple embedding provider from chat `llm_provider`.
  - Keep `HashEmbedder` as local/test default.
  - Add OpenAI-compatible embedding provider path behind explicit config and secret validation.
  - Add `GeminiEmbedder` for `gemini-embedding-2` via `models/{model}:batchEmbedContents`, using `x-goog-api-key`, one request per input text, and response order preservation.
  - Normalize Gemini model ids so both `gemini-embedding-2` and `models/gemini-embedding-2` are valid configuration values.
  - Set Gemini `output_dimensionality` from `embedding_dim` to keep pgvector vector dimensions aligned.
  - Explicit real providers (`openai|gemini`) fail fast when neither provider-neutral nor provider-specific secret is configured; only default `hash` remains zero-secret.
  - Route real embedding requests through provider/model limiter before network calls where feasible.
- Data contract impact:
  - Chunks carry `document_id`, `chunk_index`, offsets/section metadata, provider/model/dim/index_version.
- Tests to add/update:
  - Parser tests.
  - Chunker config tests.
  - Hash embedder compatibility tests.
  - Gemini embedder request-shape and response-parsing tests with `httpx.MockTransport`, no real API call.
  - Missing/invalid embedding secret tests.
- Verification command:
  - `.venv/bin/python -m pytest tests/test_rag_service.py tests/test_secret_management.py tests/test_provider_rate_limits.py -q`
- Rollback or compatibility note:
  - If real embedding configuration is absent, hash embedding remains deterministic.

### Step 6: Implement PgVectorStore

- Files/modules:
  - `app/rag/vector_store.py`
  - possibly new `app/rag/pgvector.py` for SQL-specific helpers.
- Behavior change:
  - Implement `PgVectorStore.add()` and `PgVectorStore.search()`.
  - Support owner, knowledge base, document, metadata filters, index version, top_k, score threshold, and citation metadata.
  - Keep `InMemoryVectorStore` unchanged for unit tests.
  - Factory chooses pgvector only when `rag_vector_store=pgvector`.
- Data contract impact:
  - pgvector search becomes the persistent retrieval backend.
- Tests to add/update:
  - In-memory compatibility tests remain.
  - Postgres/pgvector integration test for add/search/top_k/filter/dimension mismatch.
- Verification command:
  - `.venv/bin/python -m pytest tests/test_vector_store.py tests/test_rag_pgvector_store.py -q`
- Rollback or compatibility note:
  - Set `RAG_VECTOR_STORE=memory` to bypass pgvector.

### Step 7: Implement RAG Application Service

- Files/modules:
  - new `app/rag/service.py`
  - `app/rag/retriever.py`
  - `app/runtime/adapters.py`
  - `app/runtime/deps.py`
- Behavior change:
  - Add `RAGIngestionService.ingest_document(job_id, document_id)`.
  - Add `RAGQueryService.query(user_id, knowledge_base_id, query, top_k, filters, agent_run_id, conversation_id, strict)`.
  - Enforce owner/status.
  - Apply timeout/degraded behavior.
  - Write retrieval logs with query hash/preview, chunk ids, scores, latency, degraded reason.
  - Return `KnowledgeSearchResult[]` with citations.
  - Make `RetrieverAdapter` call the persistent service when `knowledge_base_id` is bound; otherwise return degraded empty/no knowledge base.
- Data contract impact:
  - Service becomes the stable internal interface between API, Agent tool, and repositories.
- Tests to add/update:
  - Service tests for success, empty result, disabled KB, unauthorized KB, timeout, provider limit degradation, log writes, and no-DB-during-embedding hook.
- Verification command:
  - `.venv/bin/python -m pytest tests/test_rag_service.py tests/test_rag_agent_tool.py -q`
- Rollback or compatibility note:
  - Adapter can fall back to in-memory retriever if `rag_enabled=false`.

### Step 8: Add RAG API Router

- Files/modules:
  - new `app/api/routers/rag.py`
  - `app/api/lifespan.py` or app router registration module.
  - `docs/API.md` optional update.
- Behavior change:
  - Add endpoints:
    - `POST /rag/knowledge-bases`
    - `GET /rag/knowledge-bases`
    - `GET /rag/knowledge-bases/{knowledge_base_id}`
    - `POST /rag/documents`
    - `GET /rag/documents/{document_id}`
    - `GET /rag/ingestion-jobs/{job_id}`
    - `POST /rag/query`
  - Use existing simple auth/user extraction pattern.
  - `POST /rag/documents` writes DB rows and enqueues ingestion task; it does not parse/embed inline.
  - Strict query API returns structured errors; Agent service path degrades.
- Data contract impact:
  - Adds internal/public RAG API surface.
- Tests to add/update:
  - API tests for auth, validation, owner mismatch, duplicate replay, status reads, query responses.
- Verification command:
  - `.venv/bin/python -m pytest tests/test_rag_api.py -q`
- Rollback or compatibility note:
  - Router can be disabled by `RAG_ENABLED=false` or not registered.

### Step 9: Add RAG Worker Task

- Files/modules:
  - `app/tasks/agent_tasks.py`
  - `app/tasks/celery_app.py`
  - `Makefile` if queue helpers need a RAG worker command.
- Behavior change:
  - Add `rag_ingest_document(job_id, document_id)` task routed to `q.rag`.
  - Mark job/document running/succeeded/failed.
  - Retry transient embedding/DB failures within existing retry budget.
  - Keep errors sanitized.
- Data contract impact:
  - `rag_ingestion_job` is the durable state for ingestion.
- Tests to add/update:
  - Worker tests with fake service and Celery eager/synchronous invocation if available.
- Verification command:
  - `.venv/bin/python -m pytest tests/test_rag_service.py tests/test_worker_provider_limits.py -q`
- Rollback or compatibility note:
  - Existing `run_agent_task` behavior remains unchanged.

### Step 10: Wire Agent Tool Context And Prompt Guidance

- Files/modules:
  - `app/runtime/agent_factory.py`
  - `app/runtime/orchestrator.py`
  - `app/runtime/deps.py`
  - `app/runtime/adapters.py`
  - `app/api/routers/chat.py`
- Behavior change:
  - Extend Agent deps/runtime request context with:
    - `user_id`
    - `conversation_id`
    - `agent_run_id`
    - `knowledge_base_id | None`
  - Capture `metadata.knowledge_base_id` from Chat request into run plan/meta.
  - Keep LLM-facing `search_knowledge(query)` schema stable.
  - If no knowledge base is bound, tool returns degraded empty result, not guessed content.
  - Prompt instructs Agent to cite retrieved source ids and avoid invented citations.
- Data contract impact:
  - `agent_run.plan` records RAG binding and degraded reason when applicable.
  - `tool_call_log` still records tool invocation; `rag_retrieval_log` records retrieval details.
- Tests to add/update:
  - Agent tool tests for bound KB, no KB, degraded retrieval, citation shape, and existing mock behavior.
  - Chat routing test for `metadata.knowledge_base_id` persistence.
- Verification command:
  - `.venv/bin/python -m pytest tests/test_rag_agent_tool.py tests/test_agent_factory.py tests/test_orchestrator.py tests/test_chat_routing.py -q`
- Rollback or compatibility note:
  - If RAG is disabled or no KB is bound, Chat still runs without retrieval.

### Step 11: Add DockerHost pgvector Adapter And Smoke Script

- Files/modules:
  - new `dockerhost/compose.yaml`
  - new `dockerhost/template.yaml`
  - new `dockerhost/env.example`
  - optional new `scripts/smoke_rag_pgvector.sh`
  - optional `.artifacts` output convention in smoke script.
- Behavior change:
  - Define remote integration stack with:
    - pgvector-enabled Postgres service `db`
    - Redis service `cache`
    - optional API/worker services if the app stack is ready.
  - Use `expose:` instead of fixed `ports:`.
  - Use named `postgres-data` managed volume.
  - Include healthchecks.
  - Smoke verifies `CREATE EXTENSION vector`, table creation, ingest, and query.
- Data contract impact:
  - Adds deployment adapter only; no runtime API change.
- Tests to add/update:
  - `envctl check-project --dir /Users/chris/AiProject/general-agent-ai`
  - `envctl validate-template --dir /Users/chris/AiProject/general-agent-ai/dockerhost`
- Verification command:
  - `source /Users/chris/.codex-local/dockerhost/envctl_env.sh && envctl validate-template --dir /Users/chris/AiProject/general-agent-ai/dockerhost`
- Rollback or compatibility note:
  - DockerHost adapter is additive and can be removed without affecting local development.

### Step 12: Docs, Harness Evidence, And Release Gate

- Files/modules:
  - `docs/RAG_SOLUTION.md`
  - `docs/API.md`
  - `README.md` if setup commands change.
  - `scripts/verify_release.sh` only if new required smoke hooks are ready.
- Behavior change:
  - Align docs with implemented phase-1 behavior.
  - Record DockerHost smoke as optional evidence until stable in CI/release gate.
  - Keep spec and implementation plan synchronized with any implementation discoveries.
- Data contract impact:
  - Documentation only.
- Tests to add/update:
  - Existing spec/harness validators should pass.
- Verification command:
  - `bash scripts/check_spec_contract.sh`
  - `bash scripts/check_harness_workflows.sh`
  - `AI_BOUNDARY_APPROVED=1 make verify-release`
- Rollback or compatibility note:
  - Documentation rollback does not affect runtime.

## Risk Controls

- Public contract risks:
  - `/rag/*` introduces new API surface. Keep it additive, authenticated, and owner-scoped.
  - Keep `search_knowledge(query)` LLM-facing tool schema stable; server-side context supplies KB binding.
- Security risks:
  - RAG content may contain private data. Never log full content, full query text, raw embeddings, provider secrets, or DockerHost tokens.
  - Metadata filters must be allowlisted; no raw SQL/JSON path injection.
  - Agent tool calls must enforce owner scope even though they are internal.
- Migration/rebuild risks:
  - pgvector extension may be unavailable in generic Postgres images. DockerHost adapter must use a pgvector-enabled image.
  - Additive tables are safe, but `vector(dim)` ties schema to embedding dimension. Changing production embedding dimension requires a new index version or migration plan.
  - HNSW/IVFFlat index creation can be expensive; keep smoke dataset small and production index rollout explicit.
- Performance risks:
  - Query embedding and pgvector search sit on the Agent tool hot path. Use short timeout and degraded fallback.
  - Ingestion must release DB connections before embedding network calls.
  - Retrieval logging must not happen inside vector-search transaction.
- Deployment/test-branch risks:
  - DockerHost deploys from pushed Git refs. Do not expect uncommitted local adapter changes to deploy.
  - `postgres-redis` built-in template should not be assumed to contain pgvector.
  - Clean up disposable environments with `envctl down`.
- Unrelated local changes to avoid:
  - Do not stage unrelated RAG solution edits unless intentionally included with the RAG doc/spec/plan commit.
  - Do not modify provider guardrails outside embedding admission integration required by this spec.
  - Do not weaken release, spec, or harness gates.

## Completion Criteria

- All phase-1 files from this plan are implemented or explicitly deferred in a spec update.
- Specification still matches implementation.
- Focused tests pass:
  - `.venv/bin/python -m pytest tests/test_rag_*.py tests/test_vector_store.py -q`
  - `.venv/bin/python -m pytest tests/test_agent_factory.py tests/test_orchestrator.py tests/test_chat_routing.py -q`
- Harness gates pass:
  - `git diff --check`
  - `bash scripts/check_spec_contract.sh`
  - `bash scripts/check_harness_workflows.sh`
  - `AI_BOUNDARY_APPROVED=1 make verify-release`
- DockerHost pgvector smoke is either passed and recorded or explicitly reported as blocked with reason.
- Code review findings are fixed or explicitly accepted.
- No real provider secrets, DockerHost tokens, raw private documents, or generated `.artifacts` contents are committed.
