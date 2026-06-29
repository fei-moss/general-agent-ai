# Harness Workflows

This project now has two Harness layers:

1. **Release harness:** hard, tool-neutral verification in `scripts/verify_release.sh`.
2. **Task workflow harness:** documented `HARNESS-*` execution shapes for deciding when AI work should stay single-context and when it should use specs, parallel agents, worktrees, adversarial review, loops, quarantine, model routing, or tournaments.

Dynamic workflows guide how work is performed. They do not replace release gates, owner approval, provider guardrails, or secret hygiene.

This framework is now article-driven: the source set and adopted principles are encoded in `docs/harness-workflows.json`, then tested against virtual requirements in `docs/harness-virtual-requirements.json`.

## Current Gap Analysis

| Area | Existing before this upgrade | Gap | Applied update |
| --- | --- | --- | --- |
| Release gate | `scripts/verify_release.sh` runs AI boundaries, spec contract, import smoke, pytest, optional gitleaks. | No dynamic workflow validation. | Added `scripts/check_harness_workflows.sh` and wired it into release verification. |
| Spec discipline | `check_spec_contract.sh` requires specs/plans when runtime-sensitive files change. | Specs/plans did not have to declare which Harness workflow governs the work. | Specs and implementation plans now require `Workflow Class: HARNESS-*`. |
| AI guidance | `.ai-boundaries.yml` existed, but no root project instruction source. | Codex/Claude/project rules could drift or be implicit. | Added `AGENTS.md` and `CLAUDE.md -> AGENTS.md`. |
| Dynamic task patterns | Prior plans referenced reusable Harness ideas from the Go template. | Patterns were prose, not reusable or machine-checked. | Added `docs/harness-workflows.json` with reusable workflow classes. |
| New-demand development | Spec-first workflow existed in practice. | A new feature could still omit workflow classification. | Validator fails unbound specs/plans. |
| Article-derived strategy | The first pass captured workflow classes. | It did not yet encode context management, tool-surface stability, task state, artifact strategy, or source traceability from Thariq's P0/P1 posts. | Manifest now requires source IDs, adopted principles, context/tool/state/artifact strategy, and virtual requirement coverage. |

## Source Reading Set

The current P0/P1 source set is:

| Priority | Source | Adopted theme |
| --- | --- | --- |
| P0 | `dynamic-workflows` | Classify-and-act, fan-out/synthesis, adversarial verification, tournament, loop-until-done, quarantine, model routing, budgets. |
| P0 | `skills` | Skills are folders with gotchas, scripts, assets, setup, memory, hooks, and progressive disclosure. |
| P0 | `prompt-caching` | Stable prompt/tool prefix, dynamic updates in messages, no mid-session tool mutation, cache-safe forks. |
| P0 | `seeing-like-agent` | Design tools from the model's point of view, prefer agentic search and progressive disclosure, revisit constraining tools. |
| P0 | `agent-sdk` | Give agents a computer, use file-system context, subagents, compaction, concrete feedback, visual feedback, and cautious judges. |
| P1 | `session-management` | Start fresh for new tasks, rewind bad paths, compact with hints, use subagents when only conclusions matter. |
| P1 | `html-artifacts` | Use HTML for dense specs, visual comparison, PR review, reports, custom editors, and exportable human decisions. |
| P1 | `tasks` | Replace flat todos with durable task graphs carrying dependencies, blockers, metadata, and shared session state. |
| P1 | `playgrounds` | Use standalone HTML playgrounds for interaction patterns that text cannot express well. |
| P1 | `prototyping` | Use cheap multi-variant prototypes before converging on a design or interaction. |

## Core Patterns

| Pattern | Meaning |
| --- | --- |
| `classifier-routing` | Classify the task before choosing workflow, model, or next action. |
| `fanout-barrier-synthesis` | Split work into parallel slices, wait for all results, then synthesize. |
| `adversarial-verification` | Verify outputs with a separate pass or agent against a rubric. |
| `tournament-selection` | Let multiple alternatives compete through pairwise judgment. |
| `loop-until-done` | Repeat until a stop condition is met, not for a fixed number of passes. |
| `quarantine` | Separate agents that read untrusted content from agents that perform privileged writes. |
| `model-routing` | Choose model intelligence based on expected complexity and tool-call shape. |
| `worktree-isolation` | Run broad or risky slices in isolated worktrees before synthesis. |
| `token-budget` | Declare budget and parallelism before increasing compute. |
| `resumable-evidence` | Write durable artifacts so interrupted work can be resumed or audited. |
| `progressive-disclosure` | Put details in discoverable files, references, scripts, assets, or subagents instead of frontloading context. |
| `agentic-search` | Let the agent search files, logs, or sources transparently before adding opaque semantic retrieval. |
| `task-graph` | Track work as durable tasks with dependencies, blockers, state, and evidence. |
| `cache-safe-forking` | Preserve the parent prompt/tool prefix when compacting or delegating. |
| `stable-tool-prefix` | Keep the tool set stable inside a session; route behavior through messages, modes, or deferred loading. |
| `deferred-tool-loading` | Keep lightweight tool stubs stable and load heavy schemas only when selected. |
| `human-in-loop-artifacts` | Use reviewable artifacts when humans need to inspect, compare, tune, or export decisions. |
| `concrete-feedback` | Prefer rules, tests, screenshots, linters, and state assertions before fuzzy judging. |
| `visual-feedback` | Use rendered screenshots or interactive checks when visual output affects correctness. |
| `generate-and-filter` | Generate many candidates, dedupe and filter them against a rubric before returning a shortlist. |

## Conflict Resolution

| Tension | Decision |
| --- | --- |
| Dynamic workflows can choose models/tools, but prompt caching warns against changing tools mid-session. | Workflows may route models through subagents and deferred loading, but `tool_policy.tool_mutation` must stay `stable-prefix-or-deferred-loading`. |
| Rich workflows improve quality, but dynamic workflows cost more tokens. | Every workflow declares `budget`; small edits stay in `HARNESS-FOCUSED-CHANGE`. |
| Skills should guide Claude, but over-specific skills can railroad it. | Skills and workflows specify triggers, gotchas, stop conditions, and evidence, while leaving implementation choices open. |
| Agentic search is transparent, but semantic search can be faster. | Default to agentic search; add semantic retrieval only when speed or recall variation justifies its maintenance cost. |
| LLM-as-judge can help, but it is not robust enough alone. | Use concrete feedback first; adversarial or judge agents sit behind rubrics and evidence. |
| HTML artifacts are easier to review, but release readiness needs durable evidence. | HTML/playgrounds are human review surfaces; release proof still flows through `.artifacts/` and `scripts/verify_release.sh`. |
| Durable task graphs help long work, but are overhead for tiny edits. | `task_graph` is required only for long-run, broad, security, or incident workflows; focused changes use none. |

## Workflow Classes

### HARNESS-FOCUSED-CHANGE

Use for narrow edits that fit in one context window and do not change runtime semantics.

### HARNESS-SPEC-FIRST-FEATURE

Use for behavior, API, runtime, task, config, provider-limit, secret-management, persistence, or event-contract changes. Write or update the spec first, plan from the spec, implement, review, and prove readiness with release evidence.

### HARNESS-WIDE-REFACTOR

Use for broad naming, call-site, module, or package refactors. Slice the work, use isolated worktrees when useful, review each slice, synthesize, and run release verification.

### HARNESS-DEEP-VERIFICATION

Use when specs, reports, release notes, or architecture claims must be checked against code, logs, docs, or external evidence.

### HARNESS-RESEARCH-SYNTHESIS

Use for broad source-backed research, including architecture investigations and operational reviews.

### HARNESS-SECURITY-REVIEW

Use for threat modeling, secret-hygiene review, exploitability analysis, auth review, or remediation review.

### HARNESS-INCIDENT-TRIAGE

Use for logs, alerts, recurring incidents, production symptoms, or root-cause analysis. Quarantine production or external evidence from privileged writes.

### HARNESS-EXPLORATION-TOURNAMENT

Use for naming, architecture alternatives, API designs, or product direction when multiple plausible options need rubric-driven selection.

### HARNESS-LONG-RUN-TASK-GRAPH

Use for multi-session or multi-subagent work where tasks have dependencies, blockers, owners, and resumable evidence.

### HARNESS-INTERACTIVE-ARTIFACT

Use when a human needs an HTML/playground-style surface to compare, tune, inspect, or export structured decisions.

### HARNESS-SKILL-EVOLUTION

Use when repeated corrections, runbooks, templates, scripts, and gotchas should become reusable skills or project guidance.

## Binding Rule

Every non-template specification under `docs/specifications/` and every implementation plan under `docs/implementation-plans/` must include:

```text
Workflow Class: `HARNESS-...`
```

`scripts/check_harness_workflows.sh` enforces that each binding points to a workflow class in `docs/harness-workflows.json`.

## Virtual Requirement Tests

`docs/harness-virtual-requirements.json` contains synthetic requests that exercise the framework:

- small focused edit
- API behavior change
- broad refactor
- factual claim verification
- source-backed research
- security review
- incident triage
- naming tournament
- multi-session platform upgrade
- interactive feature-flag editor
- recurring-review skill evolution

The validator fails if a virtual request points to a missing workflow, requires a pattern the workflow does not declare, or expects missing context/tool/state/artifact strategy.

## Evidence Contract

Workflow evidence should live under `.artifacts/` and may include release summaries, focused test logs, per-slice notes, claim verification tables, source lists, review rubrics, and unresolved blocker lists. Chat summaries are useful context, but they are not release evidence.
