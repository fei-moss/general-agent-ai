# Harness Workflow Invariants

Spec ID: `SPEC-HARNESS-WORKFLOW-001`

Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`

- Every reusable workflow class has a stable `HARNESS-*` ID.
- Every workflow class defines source IDs, adopted principle IDs, triggers, patterns, context strategy, tool policy, state strategy, artifact strategy, isolation, verification, stop conditions, evidence, budgets, and human escalation conditions.
- Every source ID and adopted principle ID is documented in `docs/harness-source-analysis.md`.
- Dynamic workflows may guide execution, but `scripts/verify_release.sh` remains the prerelease authority.
- Broad, adversarial, runtime-legibility, eval-improvement, or long-running tasks must separate execution from verification.
- Workflows that read untrusted external content must quarantine those readers from high-privilege write actions.
- Workflow evidence must be artifact-backed under `.artifacts/`, not only described in chat or markdown.
- Approval-required and forbidden AI boundary rules remain binding regardless of workflow class.
- Token budget and parallelism expectations must be explicit before spawning multiple agents.
- A workflow with unknown work volume must use stop conditions rather than a fixed number of passes.
- Long-running work must keep a task graph, ledger, or handoff record that lets a fresh session determine current state and next action.
- Runtime-legibility work must expose deterministic commands or evidence for startup, smoke testing, logs, metrics, traces, UI state, or equivalent feedback.
- Repeated agent failure modes must be converted into evals, tests, scripts, hooks, skills, or documented reviewer checks when feasible.
- Skill-oriented workflows must use progressive disclosure: concise triggers first, references and scripts loaded only when needed.
- Cache-safe context practices must not weaken release gates, sandbox boundaries, quarantine, approval-required paths, provider guardrails, or source verification.
