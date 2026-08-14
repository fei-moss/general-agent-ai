---
spec_id: SPEC-MARKETPLACE-TRADING-CONTEXT-001
module: marketplace_trading_context
status: implemented
workflow_class: HARNESS-SPEC-FIRST-FEATURE
---

# Marketplace Trading Context

## Specification

### Behavior

- `SPEC-MARKETPLACE-TRADING-CONTEXT-001-R1`: before the model loop starts for
  either a realtime or Celery batch run, and only after provider-quota
  admission succeeds, the orchestrator fetches the current Agent's Marketplace
  `ai-context` exactly when server-owned `run_context` resolves a valid Agent
  address, trusted `MarketplaceViewerContext` is present, and the Marketplace
  AI client is configured. A missing gate or rejected provider admission skips
  the fetch and preserves the existing model request.
- `SPEC-MARKETPLACE-TRADING-CONTEXT-001-R2`: a successful prefetch is carried in
  a server-only `AgentDeps` field and exposed through a new per-run instruction
  as data, not instructions. The compact projection is always valid JSON under
  a hard 4000-character cap: it emits bounded Agent summary and metrics first,
  including `initial_share_price`, `mint_price`, `exchange_rate`,
  `accept_token_symbol`, `aum_usd`, `volume_24h_usd`, and `holders_count`; then
  fills the remaining budget with recent report text followed by live
  activities. An individually shortened report carries `truncated: true`, and
  the data-handling prefix remains outside the bounded JSON. The result is
  never merged into `run_context`.
- `SPEC-MARKETPLACE-TRADING-CONTEXT-001-R3`: the instruction excludes
  `user_context` and defensively redacts the trusted viewer user id and wallet
  wherever they occur. Viewer identity, credentials, raw tokens, and secrets
  do not appear in prompts, logs, persisted plans, events, or public errors.
- `SPEC-MARKETPLACE-TRADING-CONTEXT-001-R4`: timeout, HTTP, invalid-response,
  unavailable, and unexpected exception outcomes fail open for chat: no
  trading-context instruction is emitted and the prefetch itself resolves
  after no more than the Marketplace client's configured request timeout. A
  subsequent model context-tool request remains independently governed by its
  existing timeout and the successful-only reuse rule in R5.
- `SPEC-MARKETPLACE-TRADING-CONTEXT-001-R5`: prefetch is server orchestration,
  not a model tool call, and does not increment or consume the existing
  `marketplace_agent_context` or `marketplace_agent_compute` call budgets. Both
  tools remain available under their existing permissions and limits. The
  default context-tool request may reuse only a successful prefetch; an
  unsuccessful prefetch or a non-default `reports_limit`/`include_raw` request
  performs the tool's existing fresh read.
- `SPEC-MARKETPLACE-TRADING-CONTEXT-001-R6`: output validation treats the
  successful prefetched result as typed current-Agent context, so claims
  grounded in its metrics, reports, or activities are not rejected merely
  because the model did not call a Marketplace tool.
- `SPEC-MARKETPLACE-TRADING-CONTEXT-001-R7`: when a successful response contains
  no recent reports and no live activities, the instruction explicitly states
  that no recent trading data was returned and does not infer that the Agent
  never traded or has no positions.

### Invariants

- The Agent address comes only from `extract_current_agent_ref(run_context)`;
  viewer identity comes only from the typed execution-bound viewer context.
- Prefetched Marketplace data remains transient in runtime memory. It is not
  written to `run_context`, run plans, message history, or streaming events.
- Marketplace calls remain read-only and keep the existing timeout, trusted
  identity-header, redaction, provider admission, and model-tool budget
  contracts.
- No trade, wallet operation, signature, schema migration, new credential, or
  deployment/configuration change is introduced.

### Performance And Compatibility

- Quota-admitted eligible runs add at most one proactive `ai-context` request
  before the model loop, bounded by the existing Marketplace client timeout.
- Runs without a current Agent, trusted viewer context, configured client, or
  successful response emit no new instruction block and retain prior behavior.
- `DEFAULT_CHAT_BEHAVIOR_POLICY`, public API shapes, Celery payloads, streaming,
  replay, ownership, and idempotency semantics remain unchanged.
- Rollback is a code revert; no data rollback is required.

## Implementation Plan

1. Add failing tests for realtime/batch gating, real response-field projection,
   section-budgeted valid JSON under the 4000-character cap, identity
   redaction, fail-open behavior, successful-only prefetch reuse, non-default
   fresh reads, budget isolation, validator compatibility, and the explicit
   zero state.
2. Add a configured-client signal, bounded projection helper, and server-only
   `AgentDeps` field; register the new `@agent.instructions` function.
3. After provider-quota admission, prefetch once in orchestration before the
   model loop and fall back silently on unsuccessful or exceptional results
   without logging identity values.
4. Reuse the prefetched typed result in output validation without modifying
   model tool counters, permissions, or public payloads.
5. Run focused tests, spec registry/contract checks, full pytest, and the
   project release gate; record evidence below.

## Closeout Evidence

- Tests-first RED: `.venv/bin/python -m pytest -q
  tests/test_marketplace_trading_context.py` reported 17 expected feature
  failures before implementation (missing configured state, renderer, deps
  field, prefetch helper/integration, fail-open behavior, and validator path).
- Follow-up tests-first RED: the verifier regression suite reproduced missing
  real response share fields and failed-prefetch cache poisoning as two focused
  failures. An additional hostile escaped-text case reproduced the invalid
  over-cap base projection before encoded-length bounding was added.
- Cycle-2 tests-first RED: a quota-rejected current-Agent run reproduced one
  unwanted Marketplace prefetch before provider admission.
- Focused tests: `tests/test_marketplace_trading_context.py` passes 21/21 after
  the follow-up corrections. The Marketplace client, Agent tool, orchestrator,
  viewer-context, tool-context, and trading-context related suite passes 153
  tests. Full `.venv/bin/python -m pytest -q` passes with the single existing
  skip.
- Review or approval:
  `AI_BOUNDARY_APPROVAL_EVIDENCE=owner-request:agent-trading-context-20260814`
- Security review: the prompt projection excludes identity/secret keys and
  `user_context`, recursively redacts trusted viewer values, contains no
  secret-shaped fixture, and exception logging records only the exception type.
- Governance: `scripts/check_spec_contract.sh` passes, and
  `HARNESSCTL_BIN="$PWD/.tools/bin/harnessctl"
  scripts/check_spec_registry.sh` passes with the installed pinned
  `harnessctl v0.3.0`. `scripts/verify_release.sh` was attempted with that local
  binary but exited before verification because `VERIFY_COMPARE_REF` is
  required and no comparison ref was supplied. No gate was weakened or
  replaced.
- Release command: `HARNESS_ARTIFACT_DIR=/private/tmp/general-agent-ai-release-20260814
  PY=.venv/bin/python scripts/check_project_release.sh` passed every required
  project check; optional `gitleaks` was skipped because it is not installed.
- Evidence path:
  `/private/tmp/general-agent-ai-release-20260814/project_release_summary.json`.
- Residual risk: quota-admitted eligible turns add one Marketplace request
  bounded by the existing eight-second default timeout. The default model
  context-tool call reuses a successful prefetched result; an unsuccessful
  prefetch or explicit non-default reports/raw request can still issue its
  existing additional read request, independently bounded by that timeout.
