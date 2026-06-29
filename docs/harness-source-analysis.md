# Harness Source Analysis

This file records the official OpenAI, Anthropic, Claude, and Codex sources that shape this repository's Harness contract. The executable source of truth is `docs/harness-workflows.json`; this document keeps the source and principle mapping reviewable.

## Official Source Set

| Source ID | Provider | Source |
| --- | --- | --- |
| `openai-harness-engineering` | OpenAI | https://openai.com/index/harness-engineering/ |
| `openai-codex-agent-loop` | OpenAI | https://openai.com/index/unrolling-the-codex-agent-loop/ |
| `openai-codex-manual` | OpenAI | https://developers.openai.com/codex/codex-manual.md |
| `claude-dynamic-workflows` | Anthropic | https://claude.com/blog/a-harness-for-every-task-dynamic-workflows-in-claude-code |
| `claude-long-running-agents` | Anthropic | https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents |
| `claude-long-running-apps` | Anthropic | https://www.anthropic.com/engineering/harness-design-long-running-apps |
| `claude-skills` | Anthropic | https://claude.com/blog/lessons-from-building-claude-code-how-we-use-skills |
| `claude-prompt-caching` | Anthropic | https://claude.com/blog/lessons-from-building-claude-code-prompt-caching-is-everything |
| `claude-html-artifacts` | Anthropic | https://claude.com/blog/using-claude-code-the-unreasonable-effectiveness-of-html |

## Adopted Principles

| Principle ID | Repository meaning | Main sources |
| --- | --- | --- |
| `source-traceability` | Harness classes and principles point back to official sources. | `openai-harness-engineering`, `claude-dynamic-workflows` |
| `release-gate-hard-authority` | Dynamic workflows guide execution, but `scripts/verify_release.sh` stays the final release authority. | `openai-codex-manual`, `openai-harness-engineering` |
| `map-not-encyclopedia` | Root instructions stay concise and link to durable docs, specs, and scripts. | `openai-harness-engineering`, `openai-codex-manual` |
| `agent-legible-environment` | Agents need direct access to app state, logs, metrics, traces, run commands, and deterministic feedback. | `openai-harness-engineering`, `claude-long-running-agents`, `claude-long-running-apps` |
| `incremental-task-ledger` | Long work records task state, blockers, evidence, and resumable handoffs. | `claude-long-running-agents`, `claude-long-running-apps` |
| `external-evaluator-loop` | The agent doing the work should not be the only judge of done. | `claude-dynamic-workflows`, `claude-long-running-apps`, `openai-codex-manual` |
| `cache-safe-context` | Stable prefixes, stable tool surfaces, append-only updates, and compaction hygiene protect long workflows. | `claude-prompt-caching`, `openai-codex-agent-loop` |
| `skill-progressive-disclosure` | Repeated workflows become focused skills with concise triggers and lazily loaded references or scripts. | `claude-skills`, `openai-codex-manual` |
| `sandbox-and-quarantine` | Untrusted readers, privileged actors, sandbox boundaries, and hook gates remain separate. | `claude-dynamic-workflows`, `openai-codex-manual` |
| `continuous-garbage-collection` | Repeated failures and repo drift should become tests, scripts, hooks, skills, or cleanup loops. | `openai-harness-engineering`, `claude-skills` |
| `artifact-review-surface` | Dense review artifacts, including HTML when useful, help humans and verifier agents inspect complex work. | `claude-html-artifacts`, `claude-long-running-apps` |

## Gap Audit

| Area | Previous state | Applied update |
| --- | --- | --- |
| Source traceability | The manifest carried article IDs and local principle names, but workflow classes did not bind to official source IDs and principle IDs. | `docs/harness-workflows.json` now requires `source_set`, `adopted_principles`, workflow `source_ids`, and workflow `principle_ids`. |
| Workflow coverage | The project had focused, spec-first, refactor, verification, research, security, incident, tournament, task-graph, interactive-artifact, and skill-evolution classes. | Added `HARNESS-RUNTIME-LEGIBILITY` and `HARNESS-EVAL-IMPROVEMENT-LOOP` from the latest template while keeping the project-specific interactive artifact class. |
| Pattern vocabulary | Earlier patterns covered classifier routing, fan-out, quarantine, stable tools, task graphs, and human review artifacts. | Added source tracing, cache-safe prefix, runtime feedback, trajectory review, eval loops, hook gates, skill packaging, mechanical invariants, artifact review, and human escalation. |
| Harness self-spec | The prior source of truth lived in one dated specification file. | Added `docs/specifications/harness_workflows/` fragments so the workflow system has its own checked spec evidence. |
| Validator strength | The validator checked manifest shape, virtual requirements, and spec/plan bindings. | It now also checks source analysis references, source URLs, adopted principles, workflow principle bindings, and Harness self-spec evidence. |

## Cooperation Rules

- Official sources explain why a workflow exists; repository authority still lives in `AGENTS.md`, specs, implementation plans, scripts, `.ai-boundaries.yml`, and release evidence.
- Dynamic workflows may increase compute only when the class declares budget, isolation, strategy, and stop conditions.
- Source traceability does not replace current-state verification. Any implementation still has to pass the release harness.
- Cache-safe context practices must not weaken sandbox boundaries, approval-required paths, provider guardrails, secret hygiene, or source verification.
- Rich artifacts are review surfaces. Release readiness still depends on `.artifacts/` evidence and `scripts/verify_release.sh`.
- Skills should stay small and triggerable; detailed gotchas, references, scripts, and examples belong behind progressive disclosure.
