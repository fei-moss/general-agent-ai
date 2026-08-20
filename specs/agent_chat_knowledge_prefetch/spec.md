---
spec_id: SPEC-AGENT-CHAT-KNOWLEDGE-PREFETCH-001
module: agent_chat_knowledge_prefetch
status: implemented
workflow_class: HARNESS-SPEC-FIRST-FEATURE
---

# Agent Chat Knowledge Prefetch

## Specification

### Behavior

- `SPEC-AGENT-CHAT-KNOWLEDGE-PREFETCH-001-R1`: after provider admission and
  before the model loop, an Ask-this-Agent turn with a typed current-Agent
  reference proactively queries the configured server-owned default knowledge
  base in-process through `RAGQueryService`. The query is the current user
  message, `top_k` is five, and its metadata language filter is `zh-CN` for a
  detected Simplified-Chinese turn or `en` for an English turn.
- `SPEC-AGENT-CHAT-KNOWLEDGE-PREFETCH-001-R2`: prefetch is skipped when the
  current-Agent reference is absent, RAG is disabled, or the server default
  knowledge-base id is empty; when `search_knowledge` is denied by server tool
  permissions; and for identity-introduction (`tool_use=none`) or Marketplace
  compute-only turns. Client-supplied knowledge-base ids do not enable or
  redirect this prefetch.
- `SPEC-AGENT-CHAT-KNOWLEDGE-PREFETCH-001-R3`: a successful, non-degraded
  retrieval with at least one chunk is carried only in server runtime memory
  and injected through a dedicated `@agent.instructions` layer. The complete
  instruction is valid JSON after its fixed prefix and no longer than 4000
  characters. Every projected chunk identifies its source document id and
  citation; shortened chunk content ends in `[TRUNCATED]` and declares
  `truncated: true`.
- `SPEC-AGENT-CHAT-KNOWLEDGE-PREFETCH-001-R4`: the prefix identifies the payload
  as server-provided `PLATFORM KNOWLEDGE`, directs the model to treat it as data
  rather than instructions, forbids guessing missing values, and states that
  typed current-Agent context wins for Agent-specific values. The platform
  layer is ordered before the existing Marketplace trading-context layer so
  both remain stable and typed current-Agent data remains authoritative.
- `SPEC-AGENT-CHAT-KNOWLEDGE-PREFETCH-001-R5`: retrieval construction, query,
  timeout, degraded, malformed, and unexpected failures are isolated from the
  Agent run and emit no instruction. Exceptions log only their type name,
  without the query, chunk content, identity, or exception message;
  non-exception degraded or empty results remain silent.
- `SPEC-AGENT-CHAT-KNOWLEDGE-PREFETCH-001-R6`: `search_knowledge` remains
  available with its existing one-call tool budget. An exact-query follow-up
  may reuse only a successful prefetched response, after prepending matching
  built-in Agent Protocol FAQ V1 chunks and reapplying `top_k` exactly as the
  existing retriever does. Unsuccessful, degraded, different-query, or
  greater-than-five-result calls use the existing retriever path. Prefetch
  applies the detected `zh-CN`/`en` metadata filter, while fresh tool retrieval
  intentionally retains the legacy unfiltered adapter behavior; documents
  without language metadata can therefore appear only on a fresh retrieval.
- `SPEC-AGENT-CHAT-KNOWLEDGE-PREFETCH-001-R7`: platform knowledge cannot change
  Marketplace, Ballot, or Hyperliquid typed-context validation. It introduces
  no new Agent address, wallet, identity, or credential projection beyond text
  already present in retrieved corpus chunks and their bounded citations.

### Invariants

- The knowledge-base id and owner scope are server settings; prefetch never
  accepts a model- or client-selected knowledge-base id.
- Retrieval remains bounded by the existing RAG timeout and fail-soft service
  behavior and occurs only after provider quota admission succeeds.
- Prefetch does not write to `run_context`, plans, message history, streaming
  events, or model-tool counters. The standard `RAGQueryService` retrieval log
  remains enabled: prefetch writes one retrieval-log row, and a subsequent
  non-reused tool retrieval writes a second row.
- Existing RAG service, API routes, tool definitions, validators, ballot logic,
  tool budgets, corpus data, and consumer golden-answer harness remain
  unchanged.
- No schema, migration, dependency, deployment, or configuration change is
  introduced.

### Performance And Compatibility

- Each eligible turn adds at most one embedding-backed RAG query before the
  model loop, using `top_k=5` and the existing RAG query timeout, plus one
  standard RAG retrieval-log row. A non-reused model tool call adds a second
  embedding query and retrieval-log row.
- At most 4000 prompt characters are added. Runs outside the gates, degraded
  queries, and empty successful queries retain prior prompt behavior.
- Rollback is a code revert; no data rollback is required.

## Implementation Plan

1. Add deterministic failing tests for gates, language filters, successful
   injection, bounded well-formed truncation, exception isolation, stable
   Marketplace composition, FAQ-preserving successful-only tool reuse,
   permission and turn-classification skips, bounded citation positions, and
   unchanged Ballot/Hyperliquid validation.
2. Add the smallest server-only dependency fields and bounded platform
   knowledge instruction renderer.
3. Add the in-process orchestrator prefetch after provider admission, using the
   default KB and language metadata convention, then pass only successful
   results to the Agent.
4. Reuse an exact successful prefetch in `search_knowledge` without changing
   its schema, availability, or call budget.
5. Run focused and full tests, spec checks, registry check, and diff hygiene;
   record closeout evidence below.

## Closeout Evidence

- Tests-first RED: `.venv/bin/python -m pytest -q
  tests/test_agent_chat_knowledge_prefetch.py` reported 13 expected feature
  failures before implementation: the in-process prefetch factory/helper,
  bounded instruction renderer, server-only dependency fields, injection
  layer, and successful-only reuse path did not exist.
- Verifier follow-up RED: five focused failures reproduced lost FAQ V1 chunks
  on exact-query reuse, missing permission and turn-classification gates, and
  complete instruction loss from oversized untyped citation positions.
- Focused tests: `tests/test_agent_chat_knowledge_prefetch.py` passes 20/20.
  The new suite plus Marketplace trading context, Agent factory, orchestrator,
  and all `tests/test_rag*.py` regressions pass 132/132.
- Full tests: `.venv/bin/python -m pytest -q` passes with the single existing
  skip. `scripts/check_project_release.sh` passes all required project checks;
  optional `gitleaks` is skipped because it is not installed.
- Review or approval:
  `AI_BOUNDARY_APPROVAL_EVIDENCE=owner-request:consumer-kb-prefetch-20260820`
- Governance: `scripts/check_spec_contract.sh` and `git diff --check` pass.
  `scripts/check_spec_registry.sh` and the registry stage of
  `scripts/verify_release.sh` were attempted but could not fetch pinned
  `harnessctl v0.3.0` because sandbox DNS could not resolve
  `proxy.golang.org`; no gate was weakened or replaced.
- Release command: `AI_BOUNDARY_APPROVAL_EVIDENCE=owner-request:consumer-kb-prefetch-20260820
  HARNESS_ARTIFACT_DIR=/private/tmp/general-agent-ai-kb-prefetch-verifier-20260820.bz5WhQ
  PY=.venv/bin/python scripts/check_project_release.sh`
- Evidence path:
  `/private/tmp/general-agent-ai-kb-prefetch-verifier-20260820.bz5WhQ/project_release_summary.json`
- Residual risk: every eligible current-Agent turn adds one embedding-backed
  query and retrieval-log row bounded by the existing RAG timeout, and adds up
  to 4000 prompt characters. A model follow-up with a different query (or more
  than five requested results) performs the existing second embedding query
  and writes a second retrieval-log row rather than reusing the prefetch.
