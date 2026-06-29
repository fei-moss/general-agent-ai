#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="$ROOT_DIR/scripts/check_harness_workflows.sh"
TMP_DIR="$(mktemp -d)"

trap 'rm -rf "$TMP_DIR"' EXIT

write_doc() {
  local file="$1"
  mkdir -p "$(dirname "$file")"
  cat >"$file" <<'DOC'
# Harness Workflows

| Pattern | Meaning |
| --- | --- |
| `classifier-routing` | Classify before acting. |
| `adversarial-verification` | Verify with a separate pass. |
| `resumable-evidence` | Store release evidence. |
| `token-budget` | Declare budget. |

## HARNESS-FOCUSED-CHANGE

Focused changes stay in one context with release evidence.

## HARNESS-SPEC-FIRST-FEATURE

Spec-first feature work binds requirements, implementation, review, and release evidence.
DOC
}

write_source_doc() {
  local file="$1"
  mkdir -p "$(dirname "$file")"
  cat >"$file" <<'DOC'
# Harness Source Analysis

| Source ID | Provider | Source |
| --- | --- | --- |
| `openai-codex-manual` | OpenAI | https://developers.openai.com/codex/codex-manual.md |

| Principle ID | Repository meaning | Main sources |
| --- | --- | --- |
| `release-gate-hard-authority` | Release remains the hard gate. | `openai-codex-manual` |
DOC
}

write_manifest() {
  local file="$1"
  mkdir -p "$(dirname "$file")"
  cat >"$file" <<'JSON'
{
  "version": 1,
  "source_set": [
    {
      "id": "openai-codex-manual",
      "provider": "OpenAI",
      "title": "Codex manual",
      "url": "https://developers.openai.com/codex/codex-manual.md",
      "status": "adopted"
    }
  ],
  "adopted_principles": [
    {
      "id": "release-gate-hard-authority",
      "summary": "Release harness remains the hard gate.",
      "source_ids": ["openai-codex-manual"]
    }
  ],
  "workflow_classes": [
    {
      "id": "HARNESS-FOCUSED-CHANGE",
      "name": "Focused Change",
      "purpose": "Use the default release harness for small scoped changes.",
      "source_ids": ["openai-codex-manual"],
      "principle_ids": ["release-gate-hard-authority"],
      "use_when": ["A change fits in one context window."],
      "patterns": ["resumable-evidence", "token-budget"],
      "context_strategy": {
        "session_boundary": "single-task-context",
        "context_rot": "start-fresh-for-new-task",
        "cache_policy": "stable-prefix",
        "subagent_policy": "none"
      },
      "tool_policy": {
        "surface": "scripts and release harness",
        "progressive_disclosure": false,
        "tool_mutation": "stable-prefix-or-deferred-loading"
      },
      "state_strategy": {
        "task_graph": "none",
        "dependencies": false,
        "resume": false
      },
      "artifact_strategy": {
        "human_review": "markdown",
        "export": "markdown",
        "evidence": ".artifacts/release/summary.json"
      },
      "isolation": {
        "worktree": "optional",
        "context": "single-agent",
        "quarantine_untrusted_inputs": false
      },
      "verification": {
        "primary_command": "scripts/verify_release.sh",
        "adversarial_review": false,
        "rubric": ["Focused tests and release gate pass."]
      },
      "stop_conditions": ["Focused verification passes."],
      "evidence": [".artifacts/release/summary.json"],
      "budget": {
        "token_budget": "bounded-by-task",
        "parallelism": "none"
      },
      "human_escalation": ["Approval-required paths are touched."]
    },
    {
      "id": "HARNESS-SPEC-FIRST-FEATURE",
      "name": "Spec-first Feature",
      "purpose": "Use a spec-backed workflow for behavior changes.",
      "source_ids": ["openai-codex-manual"],
      "principle_ids": ["release-gate-hard-authority"],
      "use_when": ["A change affects runtime behavior or contracts."],
      "patterns": ["classifier-routing", "adversarial-verification", "resumable-evidence", "token-budget"],
      "context_strategy": {
        "session_boundary": "start-fresh-for-new-behavior",
        "context_rot": "compact-with-explicit-hints",
        "cache_policy": "stable-prefix-dynamic-updates-in-messages",
        "subagent_policy": "delegate-noisy-verification"
      },
      "tool_policy": {
        "surface": "scripts, tests, and release harness",
        "progressive_disclosure": true,
        "tool_mutation": "stable-prefix-or-deferred-loading"
      },
      "state_strategy": {
        "task_graph": "optional",
        "dependencies": true,
        "resume": true
      },
      "artifact_strategy": {
        "human_review": "markdown",
        "export": "markdown",
        "evidence": ".artifacts/release/summary.json"
      },
      "isolation": {
        "worktree": "optional",
        "context": "spec-plan-implementation-review",
        "quarantine_untrusted_inputs": false
      },
      "verification": {
        "primary_command": "scripts/verify_release.sh",
        "adversarial_review": true,
        "rubric": ["Implementation follows the spec."]
      },
      "stop_conditions": ["Spec, implementation, review, and harness evidence align."],
      "evidence": [".artifacts/release/summary.json"],
      "budget": {
        "token_budget": "explicit-for-large-features",
        "parallelism": "low"
      },
      "human_escalation": ["A public API or runtime contract changes."]
    }
  ]
}
JSON
}

write_virtual_requirements() {
  local file="$1"
  mkdir -p "$(dirname "$file")"
  cat >"$file" <<'JSON'
{
  "version": 1,
  "cases": [
    {
      "id": "virtual-spec-first-feature",
      "request": "Add a new API behavior with persistence and release evidence.",
      "expected_workflow": "HARNESS-SPEC-FIRST-FEATURE",
      "required_patterns": ["classifier-routing", "adversarial-verification"],
      "required_strategies": ["context_strategy", "tool_policy", "state_strategy", "artifact_strategy"],
      "rationale": "Behavior changes must bind spec, plan, review, and release evidence."
    }
  ]
}
JSON
}

write_harness_spec_dir() {
  local dir="$1"
  mkdir -p "$dir"
  cat >"$dir/harness.md" <<'SPEC'
# Harness Binding

Spec ID: `SPEC-HARNESS-WORKFLOW-001`

Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`
SPEC
  cat >"$dir/invariants.md" <<'SPEC'
# Harness Workflow Invariants

Spec ID: `SPEC-HARNESS-WORKFLOW-001`

Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`

- Workflow classes declare stop conditions.
SPEC
}

write_bound_spec() {
  local file="$1"
  mkdir -p "$(dirname "$file")"
  cat >"$file" <<'SPEC'
# Bound Feature Specification

Spec ID: `SPEC-BOUND-FEATURE-001`

Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`

## Context

- Harness classification: spec-first feature.
SPEC
}

write_unbound_spec() {
  local file="$1"
  mkdir -p "$(dirname "$file")"
  cat >"$file" <<'SPEC'
# Unbound Feature Specification

Spec ID: `SPEC-UNBOUND-FEATURE-001`

## Context

- Harness classification: missing.
SPEC
}

write_bound_plan() {
  local file="$1"
  mkdir -p "$(dirname "$file")"
  cat >"$file" <<'PLAN'
# Bound Feature Implementation Plan

- Specification: `docs/specifications/bound-feature.md`
- Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`
PLAN
}

write_unbound_plan() {
  local file="$1"
  mkdir -p "$(dirname "$file")"
  cat >"$file" <<'PLAN'
# Unbound Feature Implementation Plan

- Specification: `docs/specifications/unbound-feature.md`
PLAN
}

run_success() {
  local name="$1"
  shift
  if "$@" >"$TMP_DIR/$name.out" 2>"$TMP_DIR/$name.err"; then
    return 0
  fi
  printf 'expected success for %s\n' "$name" >&2
  cat "$TMP_DIR/$name.err" >&2
  return 1
}

run_failure() {
  local name="$1"
  shift
  if "$@" >"$TMP_DIR/$name.out" 2>"$TMP_DIR/$name.err"; then
    printf 'expected failure for %s\n' "$name" >&2
    return 1
  fi
}

DOC="$TMP_DIR/docs/harness-workflows.md"
SOURCE_DOC="$TMP_DIR/docs/harness-source-analysis.md"
MANIFEST="$TMP_DIR/docs/harness-workflows.json"
VIRTUAL_REQUIREMENTS="$TMP_DIR/docs/harness-virtual-requirements.json"
SPECS_ROOT="$TMP_DIR/docs/specifications"
HARNESS_SPEC_DIR="$SPECS_ROOT/harness_workflows"
PLANS_ROOT="$TMP_DIR/docs/implementation-plans"

write_doc "$DOC"
write_source_doc "$SOURCE_DOC"
write_manifest "$MANIFEST"
write_virtual_requirements "$VIRTUAL_REQUIREMENTS"
write_harness_spec_dir "$HARNESS_SPEC_DIR"
write_bound_spec "$SPECS_ROOT/bound-feature.md"
write_bound_plan "$PLANS_ROOT/bound-feature-plan.md"

run_success valid_binding env \
  HARNESS_WORKFLOW_MANIFEST="$MANIFEST" \
  HARNESS_WORKFLOW_DOC="$DOC" \
  HARNESS_WORKFLOW_SOURCE_DOC="$SOURCE_DOC" \
  HARNESS_WORKFLOW_VIRTUAL_REQUIREMENTS="$VIRTUAL_REQUIREMENTS" \
  HARNESS_WORKFLOW_SPEC_DIR="$HARNESS_SPEC_DIR" \
  HARNESS_WORKFLOW_SPECS_ROOT="$SPECS_ROOT" \
  HARNESS_WORKFLOW_PLANS_ROOT="$PLANS_ROOT" \
  HARNESS_WORKFLOW_ARTIFACT_DIR="$TMP_DIR/artifacts/valid" \
  "$SCRIPT"

python3 - "$MANIFEST" "$TMP_DIR/missing_stop.json" <<'PY'
import json
import sys

source, target = sys.argv[1], sys.argv[2]
data = json.load(open(source, encoding="utf-8"))
data["workflow_classes"][0].pop("stop_conditions")
json.dump(data, open(target, "w", encoding="utf-8"))
PY
run_failure missing_stop_conditions env \
  HARNESS_WORKFLOW_MANIFEST="$TMP_DIR/missing_stop.json" \
  HARNESS_WORKFLOW_DOC="$DOC" \
  HARNESS_WORKFLOW_SOURCE_DOC="$SOURCE_DOC" \
  HARNESS_WORKFLOW_VIRTUAL_REQUIREMENTS="$VIRTUAL_REQUIREMENTS" \
  HARNESS_WORKFLOW_SPEC_DIR="$HARNESS_SPEC_DIR" \
  HARNESS_WORKFLOW_SPECS_ROOT="$SPECS_ROOT" \
  HARNESS_WORKFLOW_PLANS_ROOT="$PLANS_ROOT" \
  HARNESS_WORKFLOW_ARTIFACT_DIR="$TMP_DIR/artifacts/missing_stop" \
  "$SCRIPT"

python3 - "$MANIFEST" "$TMP_DIR/unknown_pattern.json" <<'PY'
import json
import sys

source, target = sys.argv[1], sys.argv[2]
data = json.load(open(source, encoding="utf-8"))
data["workflow_classes"][0]["patterns"].append("single-context-wishful-thinking")
json.dump(data, open(target, "w", encoding="utf-8"))
PY
run_failure unknown_pattern env \
  HARNESS_WORKFLOW_MANIFEST="$TMP_DIR/unknown_pattern.json" \
  HARNESS_WORKFLOW_DOC="$DOC" \
  HARNESS_WORKFLOW_SOURCE_DOC="$SOURCE_DOC" \
  HARNESS_WORKFLOW_VIRTUAL_REQUIREMENTS="$VIRTUAL_REQUIREMENTS" \
  HARNESS_WORKFLOW_SPEC_DIR="$HARNESS_SPEC_DIR" \
  HARNESS_WORKFLOW_SPECS_ROOT="$SPECS_ROOT" \
  HARNESS_WORKFLOW_PLANS_ROOT="$PLANS_ROOT" \
  HARNESS_WORKFLOW_ARTIFACT_DIR="$TMP_DIR/artifacts/unknown_pattern" \
  "$SCRIPT"

python3 - "$MANIFEST" "$TMP_DIR/missing_sources.json" <<'PY'
import json
import sys

source, target = sys.argv[1], sys.argv[2]
data = json.load(open(source, encoding="utf-8"))
data.pop("source_set")
json.dump(data, open(target, "w", encoding="utf-8"))
PY
run_failure missing_source_set env \
  HARNESS_WORKFLOW_MANIFEST="$TMP_DIR/missing_sources.json" \
  HARNESS_WORKFLOW_DOC="$DOC" \
  HARNESS_WORKFLOW_SOURCE_DOC="$SOURCE_DOC" \
  HARNESS_WORKFLOW_VIRTUAL_REQUIREMENTS="$VIRTUAL_REQUIREMENTS" \
  HARNESS_WORKFLOW_SPEC_DIR="$HARNESS_SPEC_DIR" \
  HARNESS_WORKFLOW_SPECS_ROOT="$SPECS_ROOT" \
  HARNESS_WORKFLOW_PLANS_ROOT="$PLANS_ROOT" \
  HARNESS_WORKFLOW_ARTIFACT_DIR="$TMP_DIR/artifacts/missing_sources" \
  "$SCRIPT"

python3 - "$MANIFEST" "$TMP_DIR/unknown_source.json" <<'PY'
import json
import sys

source, target = sys.argv[1], sys.argv[2]
data = json.load(open(source, encoding="utf-8"))
data["workflow_classes"][0]["source_ids"] = ["missing-official-source"]
json.dump(data, open(target, "w", encoding="utf-8"))
PY
run_failure unknown_source env \
  HARNESS_WORKFLOW_MANIFEST="$TMP_DIR/unknown_source.json" \
  HARNESS_WORKFLOW_DOC="$DOC" \
  HARNESS_WORKFLOW_SOURCE_DOC="$SOURCE_DOC" \
  HARNESS_WORKFLOW_VIRTUAL_REQUIREMENTS="$VIRTUAL_REQUIREMENTS" \
  HARNESS_WORKFLOW_SPEC_DIR="$HARNESS_SPEC_DIR" \
  HARNESS_WORKFLOW_SPECS_ROOT="$SPECS_ROOT" \
  HARNESS_WORKFLOW_PLANS_ROOT="$PLANS_ROOT" \
  HARNESS_WORKFLOW_ARTIFACT_DIR="$TMP_DIR/artifacts/unknown_source" \
  "$SCRIPT"

python3 - "$MANIFEST" "$TMP_DIR/unknown_principle.json" <<'PY'
import json
import sys

source, target = sys.argv[1], sys.argv[2]
data = json.load(open(source, encoding="utf-8"))
data["workflow_classes"][0]["principle_ids"] = ["missing-principle"]
json.dump(data, open(target, "w", encoding="utf-8"))
PY
run_failure unknown_principle env \
  HARNESS_WORKFLOW_MANIFEST="$TMP_DIR/unknown_principle.json" \
  HARNESS_WORKFLOW_DOC="$DOC" \
  HARNESS_WORKFLOW_SOURCE_DOC="$SOURCE_DOC" \
  HARNESS_WORKFLOW_VIRTUAL_REQUIREMENTS="$VIRTUAL_REQUIREMENTS" \
  HARNESS_WORKFLOW_SPEC_DIR="$HARNESS_SPEC_DIR" \
  HARNESS_WORKFLOW_SPECS_ROOT="$SPECS_ROOT" \
  HARNESS_WORKFLOW_PLANS_ROOT="$PLANS_ROOT" \
  HARNESS_WORKFLOW_ARTIFACT_DIR="$TMP_DIR/artifacts/unknown_principle" \
  "$SCRIPT"

MISSING_SOURCE_DOC="$TMP_DIR/docs/missing-source-doc.md"
cat >"$MISSING_SOURCE_DOC" <<'DOC'
# Harness Source Analysis

No source IDs, URLs, or principle IDs here.
DOC
run_failure missing_source_doc_reference env \
  HARNESS_WORKFLOW_MANIFEST="$MANIFEST" \
  HARNESS_WORKFLOW_DOC="$DOC" \
  HARNESS_WORKFLOW_SOURCE_DOC="$MISSING_SOURCE_DOC" \
  HARNESS_WORKFLOW_VIRTUAL_REQUIREMENTS="$VIRTUAL_REQUIREMENTS" \
  HARNESS_WORKFLOW_SPEC_DIR="$HARNESS_SPEC_DIR" \
  HARNESS_WORKFLOW_SPECS_ROOT="$SPECS_ROOT" \
  HARNESS_WORKFLOW_PLANS_ROOT="$PLANS_ROOT" \
  HARNESS_WORKFLOW_ARTIFACT_DIR="$TMP_DIR/artifacts/missing_source_doc" \
  "$SCRIPT"

MISSING_DOC="$TMP_DIR/docs/missing-id.md"
cat >"$MISSING_DOC" <<'DOC'
# Harness Workflows

No workflow IDs or patterns here.
DOC
run_failure missing_doc_reference env \
  HARNESS_WORKFLOW_MANIFEST="$MANIFEST" \
  HARNESS_WORKFLOW_DOC="$MISSING_DOC" \
  HARNESS_WORKFLOW_SOURCE_DOC="$SOURCE_DOC" \
  HARNESS_WORKFLOW_VIRTUAL_REQUIREMENTS="$VIRTUAL_REQUIREMENTS" \
  HARNESS_WORKFLOW_SPEC_DIR="$HARNESS_SPEC_DIR" \
  HARNESS_WORKFLOW_SPECS_ROOT="$SPECS_ROOT" \
  HARNESS_WORKFLOW_PLANS_ROOT="$PLANS_ROOT" \
  HARNESS_WORKFLOW_ARTIFACT_DIR="$TMP_DIR/artifacts/missing_doc" \
  "$SCRIPT"

python3 - "$MANIFEST" "$TMP_DIR/missing_strategy.json" <<'PY'
import json
import sys

source, target = sys.argv[1], sys.argv[2]
data = json.load(open(source, encoding="utf-8"))
data["workflow_classes"][0].pop("context_strategy")
json.dump(data, open(target, "w", encoding="utf-8"))
PY
run_failure missing_context_strategy env \
  HARNESS_WORKFLOW_MANIFEST="$TMP_DIR/missing_strategy.json" \
  HARNESS_WORKFLOW_DOC="$DOC" \
  HARNESS_WORKFLOW_SOURCE_DOC="$SOURCE_DOC" \
  HARNESS_WORKFLOW_VIRTUAL_REQUIREMENTS="$VIRTUAL_REQUIREMENTS" \
  HARNESS_WORKFLOW_SPEC_DIR="$HARNESS_SPEC_DIR" \
  HARNESS_WORKFLOW_SPECS_ROOT="$SPECS_ROOT" \
  HARNESS_WORKFLOW_PLANS_ROOT="$PLANS_ROOT" \
  HARNESS_WORKFLOW_ARTIFACT_DIR="$TMP_DIR/artifacts/missing_strategy" \
  "$SCRIPT"

python3 - "$MANIFEST" "$TMP_DIR/mid_session_tool_mutation.json" <<'PY'
import json
import sys

source, target = sys.argv[1], sys.argv[2]
data = json.load(open(source, encoding="utf-8"))
data["workflow_classes"][0]["tool_policy"]["tool_mutation"] = "mutate-tools-mid-session"
json.dump(data, open(target, "w", encoding="utf-8"))
PY
run_failure mid_session_tool_mutation env \
  HARNESS_WORKFLOW_MANIFEST="$TMP_DIR/mid_session_tool_mutation.json" \
  HARNESS_WORKFLOW_DOC="$DOC" \
  HARNESS_WORKFLOW_SOURCE_DOC="$SOURCE_DOC" \
  HARNESS_WORKFLOW_VIRTUAL_REQUIREMENTS="$VIRTUAL_REQUIREMENTS" \
  HARNESS_WORKFLOW_SPEC_DIR="$HARNESS_SPEC_DIR" \
  HARNESS_WORKFLOW_SPECS_ROOT="$SPECS_ROOT" \
  HARNESS_WORKFLOW_PLANS_ROOT="$PLANS_ROOT" \
  HARNESS_WORKFLOW_ARTIFACT_DIR="$TMP_DIR/artifacts/mid_session_tool_mutation" \
  "$SCRIPT"

python3 - "$VIRTUAL_REQUIREMENTS" "$TMP_DIR/unknown_virtual_workflow.json" <<'PY'
import json
import sys

source, target = sys.argv[1], sys.argv[2]
data = json.load(open(source, encoding="utf-8"))
data["cases"][0]["expected_workflow"] = "HARNESS-NOT-REAL"
json.dump(data, open(target, "w", encoding="utf-8"))
PY
run_failure unknown_virtual_workflow env \
  HARNESS_WORKFLOW_MANIFEST="$MANIFEST" \
  HARNESS_WORKFLOW_DOC="$DOC" \
  HARNESS_WORKFLOW_SOURCE_DOC="$SOURCE_DOC" \
  HARNESS_WORKFLOW_VIRTUAL_REQUIREMENTS="$TMP_DIR/unknown_virtual_workflow.json" \
  HARNESS_WORKFLOW_SPEC_DIR="$HARNESS_SPEC_DIR" \
  HARNESS_WORKFLOW_SPECS_ROOT="$SPECS_ROOT" \
  HARNESS_WORKFLOW_PLANS_ROOT="$PLANS_ROOT" \
  HARNESS_WORKFLOW_ARTIFACT_DIR="$TMP_DIR/artifacts/unknown_virtual_workflow" \
  "$SCRIPT"

UNBOUND_SPECS_ROOT="$TMP_DIR/unbound/specifications"
UNBOUND_HARNESS_SPEC_DIR="$UNBOUND_SPECS_ROOT/harness_workflows"
UNBOUND_PLANS_ROOT="$TMP_DIR/unbound/implementation-plans"
write_harness_spec_dir "$UNBOUND_HARNESS_SPEC_DIR"
write_unbound_spec "$UNBOUND_SPECS_ROOT/unbound-feature.md"
write_bound_plan "$UNBOUND_PLANS_ROOT/bound-feature-plan.md"
run_failure missing_spec_workflow_binding env \
  HARNESS_WORKFLOW_MANIFEST="$MANIFEST" \
  HARNESS_WORKFLOW_DOC="$DOC" \
  HARNESS_WORKFLOW_SOURCE_DOC="$SOURCE_DOC" \
  HARNESS_WORKFLOW_VIRTUAL_REQUIREMENTS="$VIRTUAL_REQUIREMENTS" \
  HARNESS_WORKFLOW_SPEC_DIR="$UNBOUND_HARNESS_SPEC_DIR" \
  HARNESS_WORKFLOW_SPECS_ROOT="$UNBOUND_SPECS_ROOT" \
  HARNESS_WORKFLOW_PLANS_ROOT="$UNBOUND_PLANS_ROOT" \
  HARNESS_WORKFLOW_ARTIFACT_DIR="$TMP_DIR/artifacts/missing_spec_binding" \
  "$SCRIPT"

UNBOUND_PLAN_SPECS_ROOT="$TMP_DIR/unbound_plan/specifications"
UNBOUND_PLAN_HARNESS_SPEC_DIR="$UNBOUND_PLAN_SPECS_ROOT/harness_workflows"
UNBOUND_PLAN_PLANS_ROOT="$TMP_DIR/unbound_plan/implementation-plans"
write_harness_spec_dir "$UNBOUND_PLAN_HARNESS_SPEC_DIR"
write_bound_spec "$UNBOUND_PLAN_SPECS_ROOT/bound-feature.md"
write_unbound_plan "$UNBOUND_PLAN_PLANS_ROOT/unbound-feature-plan.md"
run_failure missing_plan_workflow_binding env \
  HARNESS_WORKFLOW_MANIFEST="$MANIFEST" \
  HARNESS_WORKFLOW_DOC="$DOC" \
  HARNESS_WORKFLOW_SOURCE_DOC="$SOURCE_DOC" \
  HARNESS_WORKFLOW_VIRTUAL_REQUIREMENTS="$VIRTUAL_REQUIREMENTS" \
  HARNESS_WORKFLOW_SPEC_DIR="$UNBOUND_PLAN_HARNESS_SPEC_DIR" \
  HARNESS_WORKFLOW_SPECS_ROOT="$UNBOUND_PLAN_SPECS_ROOT" \
  HARNESS_WORKFLOW_PLANS_ROOT="$UNBOUND_PLAN_PLANS_ROOT" \
  HARNESS_WORKFLOW_ARTIFACT_DIR="$TMP_DIR/artifacts/missing_plan_binding" \
  "$SCRIPT"

run_failure missing_harness_spec_dir env \
  HARNESS_WORKFLOW_MANIFEST="$MANIFEST" \
  HARNESS_WORKFLOW_DOC="$DOC" \
  HARNESS_WORKFLOW_SOURCE_DOC="$SOURCE_DOC" \
  HARNESS_WORKFLOW_VIRTUAL_REQUIREMENTS="$VIRTUAL_REQUIREMENTS" \
  HARNESS_WORKFLOW_SPEC_DIR="$TMP_DIR/missing/harness_workflows" \
  HARNESS_WORKFLOW_SPECS_ROOT="$SPECS_ROOT" \
  HARNESS_WORKFLOW_PLANS_ROOT="$PLANS_ROOT" \
  HARNESS_WORKFLOW_ARTIFACT_DIR="$TMP_DIR/artifacts/missing_harness_spec" \
  "$SCRIPT"

printf 'harness workflow validator tests passed\n'
