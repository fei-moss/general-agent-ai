#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="${PYTHON:-${PY:-python3}}"

MANIFEST="${HARNESS_WORKFLOW_MANIFEST:-$ROOT_DIR/docs/harness-workflows.json}"
DOC="${HARNESS_WORKFLOW_DOC:-$ROOT_DIR/docs/harness-workflows.md}"
VIRTUAL_REQUIREMENTS="${HARNESS_WORKFLOW_VIRTUAL_REQUIREMENTS:-$ROOT_DIR/docs/harness-virtual-requirements.json}"
SPECS_ROOT="${HARNESS_WORKFLOW_SPECS_ROOT:-$ROOT_DIR/docs/specifications}"
PLANS_ROOT="${HARNESS_WORKFLOW_PLANS_ROOT:-$ROOT_DIR/docs/implementation-plans}"
ARTIFACT_DIR="${HARNESS_WORKFLOW_ARTIFACT_DIR:-${VERIFY_ARTIFACT_DIR:-$ROOT_DIR/.artifacts/release}}"

mkdir -p "$ARTIFACT_DIR"

"$PYTHON_BIN" - "$MANIFEST" "$DOC" "$VIRTUAL_REQUIREMENTS" "$SPECS_ROOT" "$PLANS_ROOT" "$ARTIFACT_DIR" <<'PY'
import json
import re
import sys
from pathlib import Path

manifest_path = Path(sys.argv[1])
doc_path = Path(sys.argv[2])
virtual_requirements_path = Path(sys.argv[3])
specs_root = Path(sys.argv[4])
plans_root = Path(sys.argv[5])
artifact_dir = Path(sys.argv[6])

allowed_patterns = {
    "classifier-routing",
    "fanout-barrier-synthesis",
    "adversarial-verification",
    "tournament-selection",
    "generate-and-filter",
    "loop-until-done",
    "quarantine",
    "model-routing",
    "worktree-isolation",
    "token-budget",
    "resumable-evidence",
    "progressive-disclosure",
    "agentic-search",
    "task-graph",
    "cache-safe-forking",
    "stable-tool-prefix",
    "deferred-tool-loading",
    "human-in-loop-artifacts",
    "concrete-feedback",
    "visual-feedback",
}

binding_re = re.compile(r"Workflow Class:\s*`?(HARNESS-[A-Z0-9-]+)`?")
errors: list[str] = []
workflow_ids: list[str] = []
source_ids: set[str] = set()
principle_ids: list[str] = []
spec_bindings: dict[str, str] = {}
plan_bindings: dict[str, str] = {}
virtual_cases: dict[str, str] = {}


def load_text(path: Path, label: str) -> str:
    if not path.exists():
        errors.append(f"{label} not found: {path}")
        return ""
    return path.read_text(encoding="utf-8")


def non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def non_empty_list(value: object) -> bool:
    return isinstance(value, list) and bool(value)


def require_string(obj: dict, key: str, context: str) -> None:
    if not non_empty_string(obj.get(key)):
        errors.append(f"{context} requires non-empty string field '{key}'")


def require_list(obj: dict, key: str, context: str) -> None:
    if not non_empty_list(obj.get(key)):
        errors.append(f"{context} requires non-empty list field '{key}'")


doc_text = load_text(doc_path, "workflow document")

if manifest_path.exists():
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        manifest = {}
        errors.append(f"workflow manifest is invalid JSON: {exc}")
else:
    manifest = {}
    errors.append(f"workflow manifest not found: {manifest_path}")

if manifest.get("version") != 1:
    errors.append("workflow manifest version must be 1")

sources = manifest.get("source_reading_set")
if not isinstance(sources, list) or not sources:
    errors.append("workflow manifest requires a non-empty source_reading_set list")
    sources = []

for index, source in enumerate(sources):
    context = f"source_reading_set[{index}]"
    if not isinstance(source, dict):
        errors.append(f"{context} must be an object")
        continue
    source_id = source.get("id")
    if not non_empty_string(source_id):
        errors.append(f"{context} requires non-empty string field 'id'")
    elif source_id in source_ids:
        errors.append(f"duplicate source id: {source_id}")
    else:
        source_ids.add(str(source_id))
    for key in ("title", "url", "status"):
        require_string(source, key, context)
    if source.get("priority") not in {"P0", "P1", "P2"}:
        errors.append(f"{context} priority must be P0, P1, or P2")
    if non_empty_string(source.get("url")) and not str(source["url"]).startswith(("https://", "http://")):
        errors.append(f"{context} url must be absolute: {source['url']}")
    if source.get("status") not in {"read", "read-public-text", "read-official-mirror"}:
        errors.append(f"{context} status must be read, read-public-text, or read-official-mirror")

principles = manifest.get("principles")
if not isinstance(principles, list) or not principles:
    errors.append("workflow manifest requires a non-empty principles list")
    principles = []

for index, principle in enumerate(principles):
    context = f"principles[{index}]"
    if not isinstance(principle, dict):
        errors.append(f"{context} must be an object")
        continue
    principle_id = principle.get("id")
    if not non_empty_string(principle_id):
        errors.append(f"{context} requires non-empty string field 'id'")
    else:
        principle_ids.append(str(principle_id))
    require_string(principle, "decision", context)
    principle_sources = principle.get("source_ids")
    if not non_empty_list(principle_sources):
        errors.append(f"{context} requires non-empty list field 'source_ids'")
    elif isinstance(principle_sources, list):
        for source_id in principle_sources:
            if source_id not in source_ids:
                errors.append(f"{context} references unknown source id: {source_id}")

classes = manifest.get("workflow_classes")
if not isinstance(classes, list) or not classes:
    errors.append("workflow manifest requires a non-empty workflow_classes list")
    classes = []

seen: set[str] = set()
workflow_by_id: dict[str, dict] = {}
for index, workflow in enumerate(classes):
    context = f"workflow_classes[{index}]"
    if not isinstance(workflow, dict):
        errors.append(f"{context} must be an object")
        continue

    workflow_id = workflow.get("id")
    if not non_empty_string(workflow_id):
        errors.append(f"{context} requires non-empty string field 'id'")
        workflow_id = f"<missing-{index}>"
    elif not str(workflow_id).startswith("HARNESS-"):
        errors.append(f"{context} id must start with HARNESS-: {workflow_id}")
    elif workflow_id in seen:
        errors.append(f"duplicate workflow id: {workflow_id}")
    else:
        seen.add(str(workflow_id))
        workflow_ids.append(str(workflow_id))
        workflow_by_id[str(workflow_id)] = workflow

    for key in ("name", "purpose"):
        require_string(workflow, key, context)
    for key in ("source_ids", "use_when", "patterns", "stop_conditions", "evidence", "human_escalation"):
        require_list(workflow, key, context)

    workflow_sources = workflow.get("source_ids", [])
    if isinstance(workflow_sources, list):
        for source_id in workflow_sources:
            if source_id not in source_ids:
                errors.append(f"{workflow_id} references unknown source id: {source_id}")

    if doc_text and non_empty_string(workflow_id) and str(workflow_id) not in doc_text:
        errors.append(f"{workflow_id} is not documented in {doc_path}")

    patterns = workflow.get("patterns", [])
    if isinstance(patterns, list):
        for pattern in patterns:
            if pattern not in allowed_patterns:
                errors.append(f"{workflow_id} uses unknown pattern: {pattern}")
    else:
        patterns = []

    isolation = workflow.get("isolation")
    if not isinstance(isolation, dict):
        errors.append(f"{workflow_id} requires isolation object")
        isolation = {}
    worktree = isolation.get("worktree")
    if worktree not in {"none", "optional", "required"}:
        errors.append(f"{workflow_id} isolation.worktree must be none, optional, or required")
    if not non_empty_string(isolation.get("context")):
        errors.append(f"{workflow_id} isolation.context must be non-empty")
    quarantine = isolation.get("quarantine_untrusted_inputs")
    if not isinstance(quarantine, bool):
        errors.append(f"{workflow_id} isolation.quarantine_untrusted_inputs must be boolean")
    if quarantine and "quarantine" not in patterns:
        errors.append(f"{workflow_id} quarantines inputs but does not declare the quarantine pattern")

    context_strategy = workflow.get("context_strategy")
    if not isinstance(context_strategy, dict):
        errors.append(f"{workflow_id} requires context_strategy object")
        context_strategy = {}
    for key in ("session_boundary", "context_rot", "cache_policy", "subagent_policy"):
        if not non_empty_string(context_strategy.get(key)):
            errors.append(f"{workflow_id} context_strategy.{key} must be non-empty")

    tool_policy = workflow.get("tool_policy")
    if not isinstance(tool_policy, dict):
        errors.append(f"{workflow_id} requires tool_policy object")
        tool_policy = {}
    if not non_empty_string(tool_policy.get("surface")):
        errors.append(f"{workflow_id} tool_policy.surface must be non-empty")
    if not isinstance(tool_policy.get("progressive_disclosure"), bool):
        errors.append(f"{workflow_id} tool_policy.progressive_disclosure must be boolean")
    if tool_policy.get("tool_mutation") not in {"not-applicable", "stable-prefix-or-deferred-loading"}:
        errors.append(f"{workflow_id} tool_policy.tool_mutation must be not-applicable or stable-prefix-or-deferred-loading")

    state_strategy = workflow.get("state_strategy")
    if not isinstance(state_strategy, dict):
        errors.append(f"{workflow_id} requires state_strategy object")
        state_strategy = {}
    if state_strategy.get("task_graph") not in {"none", "optional", "required"}:
        errors.append(f"{workflow_id} state_strategy.task_graph must be none, optional, or required")
    if not isinstance(state_strategy.get("dependencies"), bool):
        errors.append(f"{workflow_id} state_strategy.dependencies must be boolean")
    if not isinstance(state_strategy.get("resume"), bool):
        errors.append(f"{workflow_id} state_strategy.resume must be boolean")

    artifact_strategy = workflow.get("artifact_strategy")
    if not isinstance(artifact_strategy, dict):
        errors.append(f"{workflow_id} requires artifact_strategy object")
        artifact_strategy = {}
    if artifact_strategy.get("human_review") not in {"none", "markdown", "html", "interactive-html"}:
        errors.append(f"{workflow_id} artifact_strategy.human_review must be none, markdown, html, or interactive-html")
    if artifact_strategy.get("export") not in {"none", "markdown", "json", "prompt", "diff", "html"}:
        errors.append(f"{workflow_id} artifact_strategy.export must be none, markdown, json, prompt, diff, or html")
    if not non_empty_string(artifact_strategy.get("evidence")):
        errors.append(f"{workflow_id} artifact_strategy.evidence must be non-empty")

    verification = workflow.get("verification")
    if not isinstance(verification, dict):
        errors.append(f"{workflow_id} requires verification object")
        verification = {}
    primary_command = verification.get("primary_command")
    if not non_empty_string(primary_command):
        errors.append(f"{workflow_id} verification.primary_command must be non-empty")
    elif any(ai_tool in primary_command.lower() for ai_tool in (".claude", ".codex", "claude ", "codex ")):
        errors.append(f"{workflow_id} verification.primary_command must be tool-neutral: {primary_command}")
    if not isinstance(verification.get("adversarial_review"), bool):
        errors.append(f"{workflow_id} verification.adversarial_review must be boolean")
    if not non_empty_list(verification.get("rubric")):
        errors.append(f"{workflow_id} verification.rubric must be non-empty")

    evidence = workflow.get("evidence", [])
    if isinstance(evidence, list):
        for path in evidence:
            if not isinstance(path, str) or not path.startswith(".artifacts/"):
                errors.append(f"{workflow_id} evidence path must live under .artifacts/: {path}")

    budget = workflow.get("budget")
    if not isinstance(budget, dict):
        errors.append(f"{workflow_id} requires budget object")
        budget = {}
    if not non_empty_string(budget.get("token_budget")):
        errors.append(f"{workflow_id} budget.token_budget must be non-empty")
    if not non_empty_string(budget.get("parallelism")):
        errors.append(f"{workflow_id} budget.parallelism must be non-empty")


def markdown_files(root: Path, label: str) -> list[Path]:
    if not root.exists():
        errors.append(f"{label} root not found: {root}")
        return []
    return sorted(path for path in root.rglob("*.md") if "_template" not in path.parts)


def validate_bindings(root: Path, label: str, target: dict[str, str]) -> None:
    for path in markdown_files(root, label):
        text = path.read_text(encoding="utf-8")
        match = binding_re.search(text)
        rel = path.as_posix()
        if not match:
            errors.append(f"{label} missing Workflow Class binding: {rel}")
            continue
        workflow_id = match.group(1)
        target[rel] = workflow_id
        if workflow_id not in seen:
            errors.append(f"{label} uses unknown Workflow Class {workflow_id}: {rel}")


validate_bindings(specs_root, "specification", spec_bindings)
validate_bindings(plans_root, "implementation plan", plan_bindings)

if virtual_requirements_path.exists():
    try:
        virtual_requirements = json.loads(virtual_requirements_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        virtual_requirements = {}
        errors.append(f"virtual requirements are invalid JSON: {exc}")
else:
    virtual_requirements = {}
    errors.append(f"virtual requirements not found: {virtual_requirements_path}")

if virtual_requirements.get("version") != 1:
    errors.append("virtual requirements version must be 1")

cases = virtual_requirements.get("cases")
if not isinstance(cases, list) or not cases:
    errors.append("virtual requirements require a non-empty cases list")
    cases = []

for index, case in enumerate(cases):
    context = f"virtual_requirements.cases[{index}]"
    if not isinstance(case, dict):
        errors.append(f"{context} must be an object")
        continue
    for key in ("id", "request", "expected_workflow", "rationale"):
        require_string(case, key, context)
    case_id = str(case.get("id", f"<missing-{index}>"))
    expected = case.get("expected_workflow")
    if non_empty_string(expected):
        virtual_cases[case_id] = str(expected)
    workflow = workflow_by_id.get(str(expected))
    if workflow is None:
        errors.append(f"{context} references unknown expected_workflow: {expected}")
        continue
    required_patterns = case.get("required_patterns", [])
    if not non_empty_list(required_patterns):
        errors.append(f"{context} requires non-empty list field 'required_patterns'")
        required_patterns = []
    workflow_patterns = set(workflow.get("patterns", []))
    for pattern in required_patterns:
        if pattern not in workflow_patterns:
            errors.append(f"{context} requires pattern {pattern} but {expected} does not declare it")
    required_strategies = case.get("required_strategies", [])
    if not non_empty_list(required_strategies):
        errors.append(f"{context} requires non-empty list field 'required_strategies'")
        required_strategies = []
    for strategy in required_strategies:
        if strategy not in {"context_strategy", "tool_policy", "state_strategy", "artifact_strategy"}:
            errors.append(f"{context} has unknown required strategy: {strategy}")
        elif not isinstance(workflow.get(strategy), dict):
            errors.append(f"{context} requires {strategy} but {expected} does not declare it")

artifact_dir.mkdir(parents=True, exist_ok=True)
summary = {
    "status": "failed" if errors else "passed",
    "manifest": str(manifest_path),
    "document": str(doc_path),
    "virtual_requirements": str(virtual_requirements_path),
    "source_ids": sorted(source_ids),
    "principle_ids": principle_ids,
    "workflow_ids": workflow_ids,
    "spec_bindings": spec_bindings,
    "plan_bindings": plan_bindings,
    "virtual_cases": virtual_cases,
    "errors": errors,
}
(artifact_dir / "harness_workflows.json").write_text(
    json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8",
)

if errors:
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    sys.exit(1)

print(f"harness workflow validation passed: {len(workflow_ids)} workflows, {len(spec_bindings)} specs, {len(plan_bindings)} plans")
PY
