# 2026-06-16 Harness Workflow Upgrade Specification

## Context

- Spec ID: `SPEC-HARNESS-WORKFLOW-001`
- Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`
- Source request: 将最新 Harness 核心思想和流程完整应用到 `general-agent-ai`, 对比现有能力、缺口和需要更新的部分, 并把可执行部分落地。
- Current baseline:
  - `scripts/verify_release.sh` 已作为发布前统一 release harness。
  - `scripts/check_spec_contract.sh` 已要求 runtime-sensitive 变更绑定规格或实施计划。
  - `.ai-boundaries.yml` 已区分 allowed、approval_required、forbidden 路径。
  - 现有规格和实施计划已引用 reusable Harness 思想, 但 workflow 分类仍是散落的 prose, 无统一 manifest, 也无机器校验。
- Problem:
  - 新需求进入时, 没有稳定机制先判断应使用 focused change、spec-first feature、wide refactor、deep verification、security review、incident triage、research synthesis 或 tournament exploration。
  - 规格和计划可以存在, 但不必声明执行工作流, 后续 AI 接手时容易失去“为什么用这个流程”的上下文。
  - 项目根目录缺少 checked-in AI 指令入口, Codex/Claude 等工具可能读取不同规则。
- Non-goals:
  - 不改变业务 API、事件、DB schema、provider guardrail 或 runtime 行为。
  - 不迁移 CI provider 或云部署方式。
  - 不引入某个 AI 工具专属 enforcement。

## Product Semantics

- New behavior:
  - Repository maintains a reusable workflow manifest at `docs/harness-workflows.json`.
  - Human-readable workflow guidance lives at `docs/harness-workflows.md`.
  - Article audit and conflict decisions live at `docs/harness-source-analysis.md`.
  - Virtual demand coverage lives at `docs/harness-virtual-requirements.json`.
  - Harness self-spec evidence lives at `docs/specifications/harness_workflows/`.
  - Every non-template specification under `docs/specifications/` and every implementation plan under `docs/implementation-plans/` declares exactly one `Workflow Class: HARNESS-*` binding.
  - The validator fails if a workflow class is malformed, undocumented, uses an unknown pattern, lacks official source traceability, lacks adopted principle bindings, lacks context/tool/state/artifact strategy, lacks stop conditions, lacks evidence, or is bound by a spec/plan but missing from the manifest.
  - The validator fails if a virtual requirement points to an unknown workflow or requires a pattern/strategy the workflow does not declare.
  - `scripts/verify_release.sh` runs the workflow validator and its focused tests before Python import smoke and pytest.
  - `AGENTS.md` is the checked-in project instruction source; `CLAUDE.md` is a symlink to it to avoid rule drift.
- Operator/developer workflow:
  - For small changes, run `make check-harness-workflows` before full release verification.
  - For release readiness, run `make verify-release` and use `.artifacts/release/harness_workflows.json` as durable evidence.
  - If a new task type appears, update `docs/harness-workflows.json` and `docs/harness-workflows.md` together, then bind affected specs/plans.

## Workflow Class Manifest Contract

- Manifest version is `1`.
- Manifest includes `source_set` with official OpenAI, Codex, Anthropic, and Claude source identifiers, providers, URLs, and adoption status.
- Manifest includes `adopted_principles` with `source_ids` and summaries.
- Each workflow class has:
  - `id` beginning with `HARNESS-`
  - `name`
  - `purpose`
  - `source_ids`
  - `principle_ids`
  - `use_when`
  - `patterns`
  - `context_strategy`
  - `tool_policy`
  - `state_strategy`
  - `artifact_strategy`
  - `isolation`
  - `verification`
  - `stop_conditions`
  - `evidence`
  - `budget`
  - `human_escalation`
- Allowed pattern vocabulary:
  - `classifier-routing`
  - `fanout-barrier-synthesis`
  - `adversarial-verification`
  - `generate-filter`
  - `tournament-selection`
  - `loop-until-done`
  - `quarantine`
  - `model-routing`
  - `worktree-isolation`
  - `token-budget`
  - `resumable-evidence`
  - `source-traceability`
  - `progressive-disclosure`
  - `agentic-search`
  - `task-graph`
  - `cache-safe-prefix`
  - `cache-safe-forking`
  - `stable-tool-prefix`
  - `deferred-tool-loading`
  - `artifact-review`
  - `human-in-loop-artifacts`
  - `agent-legibility`
  - `runtime-feedback`
  - `trajectory-review`
  - `eval-improvement-loop`
  - `mechanical-invariants`
  - `concrete-feedback`
  - `visual-feedback`
  - `sandbox-boundary`
  - `hook-gate`
  - `context-reset`
  - `skill-packaging`
  - `human-escalation`
  - `generate-and-filter`
- Evidence paths must live under `.artifacts/`.
- Verification primary commands must be tool-neutral scripts or make targets, not Codex/Claude-only instructions.
- Tool policy must not encode mid-session tool mutation; dynamic behavior uses stable prefixes, messages, subagents, or deferred loading.

## Source Coverage Contract

Required official sources:

- `openai-harness-engineering`
- `openai-codex-agent-loop`
- `openai-codex-manual`
- `claude-dynamic-workflows`
- `claude-long-running-agents`
- `claude-long-running-apps`
- `claude-skills`
- `claude-prompt-caching`
- `claude-html-artifacts`

The framework must explicitly resolve conflicts among these sources rather than silently merging incompatible guidance.

## Virtual Requirement Contract

`docs/harness-virtual-requirements.json` must include synthetic demands covering at least:

- focused edit
- API/runtime behavior change
- broad refactor
- deep factual verification
- source-backed research
- security review
- incident triage
- rubric/tournament exploration
- multi-session task graph
- runtime legibility
- eval improvement loop
- interactive artifact
- skill evolution

## Acceptance Criteria

- `scripts/check_harness_workflows_test.sh` proves:
  - a valid manifest and bound spec/plan pass;
  - a workflow missing `stop_conditions` fails;
  - an unknown pattern fails;
  - missing source traceability fails;
  - unknown principle bindings fail;
  - missing source-analysis references fail;
  - missing context/tool/state/artifact strategy fails;
  - mid-session tool mutation fails;
  - virtual requirements with unknown workflow fail;
  - a spec without `Workflow Class` fails;
  - an implementation plan without `Workflow Class` fails.
- `scripts/check_harness_workflows.sh` writes `.artifacts/release/harness_workflows.json` or the configured artifact path.
- `make verify-release` includes `harness_workflows` and `harness_workflow_tests` in `summary.json`.
- `docs/harness-workflows.json` validates with 9 official sources, 11 adopted principles, and at least 13 workflow classes.
- `docs/harness-virtual-requirements.json` validates all required synthetic demands against declared workflow patterns and strategies.
- `docs/specifications/harness_workflows/` references `SPEC-HARNESS-WORKFLOW-001` and declares the Harness workflow binding.
- Existing runtime and provider specs/plans are bound to `HARNESS-SPEC-FIRST-FEATURE`.
- The project instruction source is discoverable through both `AGENTS.md` and `CLAUDE.md`.
