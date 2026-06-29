# Harness Workflows

This project has two Harness layers:

1. **Release harness:** hard, tool-neutral verification in `scripts/verify_release.sh`.
2. **Task workflow harness:** documented `HARNESS-*` execution shapes for choosing when AI work should stay focused and when it should use specs, parallel agents, worktrees, adversarial review, loops, quarantine, runtime feedback, eval improvement, artifacts, or skills.

Dynamic workflows guide how work is performed. They do not replace release gates, owner approval, provider guardrails, secret hygiene, or `.ai-boundaries.yml`.

## Source Traceability

The workflow catalog is derived from official OpenAI, Codex, Anthropic, and Claude sources. The traceable source and principle matrix lives in `docs/harness-source-analysis.md`.

Every workflow class in `docs/harness-workflows.json` must declare:

- `source_ids`: official sources that justify the workflow.
- `principle_ids`: adopted principles from the source analysis.
- context, tool, state, artifact, isolation, verification, budget, evidence, and escalation strategies.

The validator checks those IDs and references so the project does not drift into undocumented agent folklore.

## Core Patterns

| Pattern | Meaning |
| --- | --- |
| `classifier-routing` | Classify the task before choosing workflow, model, agent, or next action. |
| `fanout-barrier-synthesis` | Split work into parallel slices, wait for all results, then synthesize. |
| `adversarial-verification` | Verify outputs with a separate pass or agent against a rubric. |
| `generate-filter` | Generate multiple candidates, filter against constraints, then keep only reviewed winners. |
| `generate-and-filter` | Project-local alias for generate and filter workflows. |
| `tournament-selection` | Let multiple alternatives compete through pairwise or rubric-based judgment. |
| `loop-until-done` | Repeat until a stop condition is met, not for a fixed number of passes. |
| `quarantine` | Separate agents that read untrusted content from agents that perform privileged writes. |
| `model-routing` | Choose model intelligence based on expected complexity and tool-call shape. |
| `worktree-isolation` | Run broad or risky slices in isolated git worktrees before synthesis. |
| `token-budget` | Declare budget and parallelism before increasing compute. |
| `resumable-evidence` | Write durable artifacts so interrupted work can be resumed or audited. |
| `source-traceability` | Preserve source IDs, source URLs, and principle IDs for workflow design choices. |
| `progressive-disclosure` | Keep entry instructions small and load references, scripts, or details only when needed. |
| `agentic-search` | Search files, logs, sources, and runtime state transparently before adding opaque retrieval. |
| `task-graph` | Track long work as explicit tasks, blockers, owners, dependencies, and evidence. |
| `cache-safe-prefix` | Preserve stable instructions, tool surfaces, and append-only context where possible. |
| `cache-safe-forking` | Project-local alias for cache-safe context handoff and delegation. |
| `stable-tool-prefix` | Keep tool surfaces stable inside a session; route dynamic behavior through messages or deferred loading. |
| `deferred-tool-loading` | Load heavy tool schemas only after a lightweight selector chooses them. |
| `artifact-review` | Produce dense review artifacts for human and verifier inspection when complexity justifies them. |
| `human-in-loop-artifacts` | Use reviewable artifacts when humans need to inspect, compare, tune, or export decisions. |
| `agent-legibility` | Make app state, repo maps, logs, metrics, traces, and UI state easy for agents to inspect. |
| `runtime-feedback` | Let agents run the system, interact with it, and inspect feedback from the real runtime. |
| `trajectory-review` | Review the action sequence and decisions, not only the final diff. |
| `eval-improvement-loop` | Convert repeated failures into evals, tests, scripts, hooks, or skill improvements. |
| `mechanical-invariants` | Encode repeated correctness rules in scripts, linters, tests, or CI gates. |
| `concrete-feedback` | Prefer tests, linters, screenshots, state assertions, and release gates before fuzzy judging. |
| `visual-feedback` | Use screenshots or interactive checks when visual output affects correctness. |
| `sandbox-boundary` | Keep autonomy inside explicit filesystem, network, command, approval, and credential boundaries. |
| `hook-gate` | Use lifecycle hooks or equivalent mechanical checks for repeated safety or quality gates. |
| `context-reset` | Use fresh sessions, compaction checkpoints, or handoff notes to avoid stale context. |
| `skill-packaging` | Turn repeated workflows into focused skills with triggers, references, scripts, and tests. |
| `human-escalation` | Route product, safety, credential, or irreversible decisions to a human instead of hiding assumptions. |

## Workflow Classes

### HARNESS-FOCUSED-CHANGE

Use for narrow edits that fit in one context window and do not change runtime semantics. Keep execution linear, run focused verification, then run the release harness.

### HARNESS-SPEC-FIRST-FEATURE

Use for behavior, API, runtime, task, config, provider-limit, secret-management, persistence, prompt, or event-contract changes. Write or update the spec first, plan from the spec, implement, review, and prove readiness with release evidence.

### HARNESS-WIDE-REFACTOR

Use for broad naming, call-site, module, package, or generated-example refactors. Slice the work, use isolated worktrees when useful, review each slice, synthesize, and run release verification.

### HARNESS-DEEP-VERIFICATION

Use when specs, reports, release notes, or architecture claims must be checked against code, logs, docs, or external evidence before publication or release.

### HARNESS-RESEARCH-SYNTHESIS

Use for broad source-backed research, including architecture investigations and operational reviews. Fan out evidence collection, verify source quality, synthesize with citations or local references, and preserve uncertainty.

### HARNESS-SECURITY-REVIEW

Use for threat modeling, secret-hygiene review, exploitability analysis, auth review, or remediation review. Quarantine untrusted inputs and separate discovery, validation, remediation, and review.

### HARNESS-INCIDENT-TRIAGE

Use for logs, alerts, recurring incidents, production symptoms, or root-cause analysis. Classify, dedupe, investigate, and escalate with bounded evidence.

### HARNESS-EXPLORATION-TOURNAMENT

Use for naming, architecture alternatives, API designs, product direction, or strategy options when multiple plausible answers need rubric-driven selection.

### HARNESS-LONG-RUN-TASK-GRAPH

Use for multi-session or multi-subagent work where tasks have dependencies, blockers, owners, status, evidence, and resumable handoff needs.

### HARNESS-RUNTIME-LEGIBILITY

Use when changing development environments, app startup, observability, UI feedback, logs, traces, metrics, local smoke paths, or other surfaces that make the running system legible to agents and humans.

### HARNESS-EVAL-IMPROVEMENT-LOOP

Use when repeated agent mistakes, prompt failures, flaky workflows, or review escapes should become durable tests, evals, scripts, hooks, skills, or checklist changes.

### HARNESS-INTERACTIVE-ARTIFACT

Use when a human needs an HTML or playground-style surface to compare, tune, inspect, or export structured decisions. This is a project extension of the artifact-review pattern.

### HARNESS-SKILL-EVOLUTION

Use when repeated corrections, runbooks, templates, scripts, and gotchas should become reusable skills or project guidance.

## Binding Rule

Every non-template specification under `docs/specifications/` and every implementation plan under `docs/implementation-plans/` must include:

```text
Workflow Class: `HARNESS-...`
```

`scripts/check_harness_workflows.sh` enforces that each binding points to a workflow class in `docs/harness-workflows.json`.

## Harness Self-Spec

The workflow framework itself is covered by `SPEC-HARNESS-WORKFLOW-001` under `docs/specifications/harness_workflows/`. That directory records invariants, behavior scenarios, performance expectations, and the Harness binding for future workflow changes.

## Virtual Requirement Tests

`docs/harness-virtual-requirements.json` contains synthetic requests that exercise the framework:

- small focused edit
- API or runtime behavior change
- broad refactor
- factual claim verification
- source-backed research
- security review
- incident triage
- naming tournament
- multi-session task graph
- runtime legibility
- eval improvement loop
- interactive feature-flag editor
- recurring-review skill evolution

The validator fails if a virtual request points to a missing workflow, requires a pattern the workflow does not declare, or expects missing context, tool, state, or artifact strategy.

## Evidence Contract

Workflow evidence should live under `.artifacts/` and may include release summaries, focused test logs, per-slice notes, task ledgers, claim verification tables, source lists, review rubrics, runtime smoke logs, screenshots, traces, metrics snapshots, trajectory review notes, eval output, skill trigger tests, and unresolved blocker lists.

Chat summaries are useful context, but they are not release evidence. The final prerelease authority remains `scripts/verify_release.sh`.

## Guardrails

- Approval-required paths still require owner approval.
- Forbidden paths stay forbidden.
- Workflow scripts and AI-tool wrappers must not become the only enforcement point.
- A workflow that consumes untrusted content must not directly perform privileged writes.
- A workflow that uses extra parallelism must declare budget and stop conditions first.
- Source traceability supports but does not replace current-state verification.
- Cache-safe context practices must never override sandbox, approval, credential, provider-limit, or release-gate boundaries.
- Rich artifacts are review aids, not substitutes for specs, tests, and release evidence.
