# Harness Source Analysis

This document records the P0/P1 Thariq Shihipar posts used to upgrade this repository's Harness framework. The executable adoption lives in `docs/harness-workflows.json`; this file explains why each idea was adopted and how conflicts were resolved.

## Reading Matrix

| Priority | Source ID | Source | Status | Adopted into framework |
| --- | --- | --- | --- | --- |
| P0 | `dynamic-workflows` | [A harness for every task: dynamic workflows in Claude Code](https://claude.com/blog/a-harness-for-every-task-dynamic-workflows-in-claude-code) | Read official article | Workflow classes, classifier routing, fan-out/synthesis, adversarial verification, generate/filter, tournament, loop-until-done, quarantine, model routing, budgets. |
| P0 | `skills` | [Lessons from building Claude Code: How we use skills](https://claude.com/blog/lessons-from-building-claude-code-how-we-use-skills) | Read official article | Skills as folders, gotchas, progressive disclosure, scripts/assets, setup questions, memory, hooks, model-facing descriptions. |
| P0 | `prompt-caching` | [Lessons from building Claude Code: Prompt caching is everything](https://claude.com/blog/lessons-from-building-claude-code-prompt-caching-is-everything) | Read official article | Stable prompt/tool prefix, dynamic updates via messages, model routing via subagents, deferred tool loading, cache-safe compaction. |
| P0 | `seeing-like-agent` | [Seeing like an agent: how we design tools in Claude Code](https://claude.com/blog/seeing-like-an-agent) | Read official article | Model-shaped tools, high bar for new tools, AskUserQuestion-style elicitation, task primitives, agentic search, progressive disclosure. |
| P0 | `agent-sdk` | [Building agents with the Claude Agent SDK](https://claude.com/blog/building-agents-with-the-claude-agent-sdk) | Read official article | Give agents a computer, file-system context engineering, agentic search before semantic search, subagents, compaction, concrete and visual feedback. |
| P1 | `session-management` | [Using Claude Code: session management and 1M context](https://claude.com/blog/using-claude-code-session-management-and-1m-context) | Read official article | Start fresh for new tasks, rewind failed paths, compact with hints, subagents for noisy intermediate outputs. |
| P1 | `html-artifacts` | [Using Claude Code: The unreasonable effectiveness of HTML](https://claude.com/blog/using-claude-code-the-unreasonable-effectiveness-of-html) | Read official article | HTML as high-density human review surface, visual comparison, PR review, reports, custom editors, export back to workflow. |
| P1 | `tasks` | [We are turning Todos into Tasks in Claude Code](https://x.com/trq212/status/2014480496013803643) | Read public X article text | Durable task graph, dependencies, blockers, file-system state, multi-session and multi-subagent collaboration. |
| P1 | `playgrounds` | [Making Playgrounds using Claude Code](https://x.com/trq212/status/2017024445244924382) | Read public X article text | Standalone HTML playgrounds for visualizing, tuning, commenting, and exporting prompts or structured decisions. |
| P1 | `prototyping` | [How we prototype using Claude Code](https://x.com/trq212/status/1963028819943841873) | Read public X post text; video details not transcribed | Cheap multi-variant prototypes; use artifact/tournament workflows before converging on one design. |

## Adopted Principles

1. Classify before compute: do not reflexively fan out or use heavy models for small edits.
2. Split contexts when scale, bias, or noisy output would pollute the parent context.
3. Prefer concrete feedback: tests, linters, screenshots, state assertions, and release gates beat ungrounded judging.
4. Keep the prompt/tool prefix stable; use messages, modes, subagents, or deferred loading for dynamic behavior.
5. Use progressive disclosure: references, scripts, examples, assets, runbooks, and subagents should be discovered when needed.
6. Use durable task graphs for long-running work with dependencies and blockers.
7. Use HTML/playground artifacts when human inspection, tuning, or export matters.
8. Start with transparent agentic search; add semantic search only for speed or recall tradeoffs.
9. Treat skills as folders with gotchas, setup, memory, scripts, assets, and optional hooks.
10. Compact or fork in a cache-safe way and preserve only load-bearing context.

## Conflict Audit

| Conflict | Resolution in this repository |
| --- | --- |
| Dynamic workflows can pick tools/models, while prompt caching discourages changing tool sets. | Workflows may choose models through subagents and load heavy tool schemas through deferred discovery, but the active tool surface must stay stable inside a session. |
| Dynamic workflows improve quality but can overuse tokens. | `budget` is required for every workflow, and virtual requirements include a small edit that must stay `HARNESS-FOCUSED-CHANGE`. |
| Skills should encode best practices, but over-specific skills can railroad Claude. | Workflow and skill guidance uses trigger descriptions, gotchas, stop conditions, and evidence; it avoids prescribing every implementation step. |
| Agentic search is transparent, while semantic search is faster. | Harness defaults to agentic search; semantic search is a later optimization when speed or recall variation is worth the extra maintenance. |
| LLM-as-judge is useful but weak as sole proof. | LLM judging is secondary to concrete feedback and adversarial verification against explicit rubrics. |
| HTML artifacts are rich but not release evidence by themselves. | Interactive artifacts support human review and export; release readiness still depends on `.artifacts/` and `scripts/verify_release.sh`. |
| Task graphs help long work but add overhead. | `state_strategy.task_graph` is `required` only for long-run, wide refactor, security, and incident workflows; focused changes set it to `none`. |

## Framework Changes Triggered By The Reading

- `docs/harness-workflows.json` now stores `source_reading_set` and `principles`, so the manifest is traceable to the read articles.
- Every workflow class now declares `source_ids`, `context_strategy`, `tool_policy`, `state_strategy`, and `artifact_strategy`.
- The pattern vocabulary now includes progressive disclosure, agentic search, task graphs, cache-safe forking, stable tool prefix, deferred loading, human-in-loop artifacts, concrete feedback, visual feedback, and generate/filter.
- New workflow classes:
  - `HARNESS-LONG-RUN-TASK-GRAPH`
  - `HARNESS-INTERACTIVE-ARTIFACT`
  - `HARNESS-SKILL-EVOLUTION`
- `docs/harness-virtual-requirements.json` tests the framework against synthetic demands instead of only validating JSON shape.
