# Marketplace QnA Standard Acceptance Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing Marketplace QnA acceptance tools into a concise, fail-fast five-target Makefile workflow.

**Architecture:** Keep the current fixture builder, Promptfoo config, live evaluator, release harness, and acceptance validator as the only authorities. Add a thin Makefile composition layer and point the existing runbook to it; no generic workflow engine, upload automation, deployment automation, or runtime changes.

**Tech Stack:** GNU Make, Python 3.12, pytest, Promptfoo, existing DockerHost live evaluator.

## Global Constraints

- Specification: `docs/specifications/2026-07-16-marketplace-qna-standard-workflow-specification.md` (`SPEC-RAG-EVAL-003`).
- Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`.
- Required full-run environment: `GEMINI_API_KEY`, `MARKETPLACE_QNA_BASE_URL`, and `MARKETPLACE_QNA_KNOWLEDGE_BASE_ID`.
- Persistent upload remains an explicit operator action and must already have produced `.artifacts/release/marketplace_qna_ingestion_summary.json`.
- Semantic failures are never retried into a pass.
- Existing acceptance thresholds remain defined only in `tests/rag_eval/marketplace_qna_acceptance_evidence_contract.json`.
- No runtime, API, task, database, authentication, provider, or deployment behavior changes.
- No subagents: the change is narrow, sequential, and edits one shared Makefile contract.

---

### Task 1: Define the Makefile Workflow Contract

**Files:**
- Create: `tests/test_marketplace_qna_workflow.py`
- Modify: `Makefile`

**Interfaces:**
- Consumes: existing Marketplace QnA Python modules and acceptance artifact paths.
- Produces: `marketplace-qna-preflight`, `marketplace-qna-local`, `marketplace-qna-live`, `marketplace-qna-final`, and `marketplace-qna-acceptance` Make targets.

- [ ] **Step 1: Write failing target and ordering tests**

Create tests that read `Makefile` and assert:

```python
TARGETS = (
    "marketplace-qna-preflight",
    "marketplace-qna-local",
    "marketplace-qna-live",
    "marketplace-qna-final",
    "marketplace-qna-acceptance",
)

def test_marketplace_qna_make_targets_are_declared():
    makefile = MAKEFILE.read_text(encoding="utf-8")
    for target in TARGETS:
        assert f"{target}:" in makefile

def test_marketplace_qna_aggregate_target_is_fail_fast_and_ordered():
    recipe = target_recipe("marketplace-qna-acceptance")
    commands = [
        "$(MAKE) marketplace-qna-preflight",
        "$(MAKE) marketplace-qna-local",
        "$(MAKE) marketplace-qna-live",
        "$(MAKE) marketplace-qna-final",
    ]
    assert all(command in recipe for command in commands)
    assert [recipe.index(command) for command in commands] == sorted(
        recipe.index(command) for command in commands
    )
```

Also assert preflight checks all three environment variables and the ingestion summary before invoking the fixture builder.

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest -q tests/test_marketplace_qna_workflow.py
```

Expected: fail because none of the five Make targets exists.

- [ ] **Step 3: Add the minimal Makefile variables and targets**

Add configurable artifact variables and recipes equivalent to:

```make
MARKETPLACE_QNA_BASE_URL ?=
MARKETPLACE_QNA_KNOWLEDGE_BASE_ID ?=
MARKETPLACE_QNA_INGESTION_SUMMARY ?= .artifacts/release/marketplace_qna_ingestion_summary.json

marketplace-qna-preflight:
	@test -n "$$GEMINI_API_KEY" || (echo "GEMINI_API_KEY is required" >&2; exit 1)
	@test -n "$(MARKETPLACE_QNA_BASE_URL)" || (echo "MARKETPLACE_QNA_BASE_URL is required" >&2; exit 1)
	@test -n "$(MARKETPLACE_QNA_KNOWLEDGE_BASE_ID)" || (echo "MARKETPLACE_QNA_KNOWLEDGE_BASE_ID is required" >&2; exit 1)
	@test -f "$(MARKETPLACE_QNA_INGESTION_SUMMARY)" || (echo "Marketplace QnA ingestion summary is required" >&2; exit 1)
	$(PY) tests/rag_eval/marketplace_qna_fixture_builder.py
	$(PY) -m tests.rag_eval.marketplace_qna_golden_query_audit --output .artifacts/release/marketplace_qna_golden_query_audit.json
	$(PY) -m pytest -q tests/test_marketplace_qna_eval.py tests/test_rag_promptfoo_eval.py

marketplace-qna-local:
	@test -n "$$GEMINI_API_KEY" || (echo "GEMINI_API_KEY is required" >&2; exit 1)
	$(PY) -m tests.rag_eval.moss_gemini_preflight --output .artifacts/release/marketplace_qna_gemini_preflight.json --model gemini-embedding-2 --dimension 256
	PROMPTFOO_PYTHON=$(PY) npx --yes promptfoo@latest eval -c tests/rag_eval/marketplace_qna_promptfooconfig.yaml --no-cache --output .artifacts/release/marketplace_qna_promptfoo_eval.json

marketplace-qna-live:
	@test -n "$(MARKETPLACE_QNA_BASE_URL)" || (echo "MARKETPLACE_QNA_BASE_URL is required" >&2; exit 1)
	@test -n "$(MARKETPLACE_QNA_KNOWLEDGE_BASE_ID)" || (echo "MARKETPLACE_QNA_KNOWLEDGE_BASE_ID is required" >&2; exit 1)
	$(PY) -m tests.rag_eval.marketplace_qna_live_eval --base-url "$(MARKETPLACE_QNA_BASE_URL)" --knowledge-base-id "$(MARKETPLACE_QNA_KNOWLEDGE_BASE_ID)" --retrieval-workers 4 --chat-timeout-s 120

marketplace-qna-final:
	$(MAKE) verify-release
	$(PY) -m tests.rag_eval.marketplace_qna_acceptance_validator
	$(PY) -m tests.rag_eval.marketplace_qna_acceptance_status --output .artifacts/release/marketplace_qna_acceptance_status.json

marketplace-qna-acceptance:
	$(MAKE) marketplace-qna-preflight
	$(MAKE) marketplace-qna-local
	$(MAKE) marketplace-qna-live
	$(MAKE) marketplace-qna-final
```

Add all five targets to `.PHONY` and `make help`.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run:

```bash
.venv/bin/python -m pytest -q tests/test_marketplace_qna_workflow.py tests/test_marketplace_qna_eval.py
make -n marketplace-qna-acceptance \
  GEMINI_API_KEY=redacted \
  MARKETPLACE_QNA_BASE_URL=https://example.invalid \
  MARKETPLACE_QNA_KNOWLEDGE_BASE_ID=kb_example
```

Expected: tests pass; dry-run output lists preflight, local, live, and final once in order and prints no secret value.

- [ ] **Step 5: Commit the executable workflow**

```bash
git add Makefile tests/test_marketplace_qna_workflow.py
git commit -m "test: add marketplace qna acceptance workflow"
```

### Task 2: Make the Runbook Concise and Canonical

**Files:**
- Modify: `docs/MARKETPLACE_QNA_RAG_INGESTION_RUNBOOK.md`
- Modify: `tests/test_marketplace_qna_workflow.py`

**Interfaces:**
- Consumes: the five Make targets from Task 1.
- Produces: one canonical operator command and a short explanation of the manual ingestion boundary.

- [ ] **Step 1: Write a failing runbook contract test**

Add:

```python
def test_marketplace_qna_runbook_uses_make_as_the_canonical_entrypoint():
    runbook = RUNBOOK.read_text(encoding="utf-8")
    assert "make marketplace-qna-acceptance" in runbook
    assert "make marketplace-qna-preflight" in runbook
    assert "make marketplace-qna-local" in runbook
    assert "make marketplace-qna-live" in runbook
    assert "make marketplace-qna-final" in runbook
    assert "does not upload or deploy" in runbook
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
.venv/bin/python -m pytest -q tests/test_marketplace_qna_workflow.py -k runbook
```

Expected: fail because the current runbook lists low-level commands instead of the canonical Make workflow.

- [ ] **Step 3: Add a short Standard Workflow section and remove duplicated acceptance commands**

The runbook must lead with:

```bash
source /Users/chris/.codex-local/general-agent-ai/gemini_env.sh
: "${MARKETPLACE_QNA_BASE_URL:?export the target API base URL}"
: "${MARKETPLACE_QNA_KNOWLEDGE_BASE_ID:?export the target knowledge-base id}"
make marketplace-qna-acceptance
```

List the four stage targets for diagnosis. State explicitly that Make does not upload or deploy; the operator completes the persistent import and DockerHost deployment steps before the aggregate acceptance run. Keep the detailed upload, rollback, and retention sections.

- [ ] **Step 4: Run documentation and workflow tests**

Run:

```bash
.venv/bin/python -m pytest -q tests/test_marketplace_qna_workflow.py tests/test_marketplace_qna_eval.py
scripts/check_spec_contract.sh
scripts/check_spec_registry.sh
git diff --check
```

Expected: all commands pass.

- [ ] **Step 5: Commit the canonical runbook**

```bash
git add docs/MARKETPLACE_QNA_RAG_INGESTION_RUNBOOK.md tests/test_marketplace_qna_workflow.py
git commit -m "docs: standardize marketplace qna acceptance"
```

### Task 3: Final Verification and Publication

**Files:**
- Verify only; no planned source edits.

**Interfaces:**
- Consumes: Tasks 1 and 2.
- Produces: fresh release evidence and a pushed task branch.

- [ ] **Step 1: Run all local and release gates**

```bash
make test
make verify-release
.venv/bin/python -m tests.rag_eval.marketplace_qna_acceptance_validator
.venv/bin/python -m tests.rag_eval.marketplace_qna_acceptance_status \
  --output .artifacts/release/marketplace_qna_acceptance_status.json
git diff --check
```

Expected: all commands exit 0; acceptance status is `passed` with no blockers.

- [ ] **Step 2: Verify repository state and push**

```bash
git status --short --branch
git push origin codex/zai-glm52-dockerhost
git rev-parse HEAD
git rev-parse origin/codex/zai-glm52-dockerhost
```

Expected: clean worktree and identical local/remote SHAs.
