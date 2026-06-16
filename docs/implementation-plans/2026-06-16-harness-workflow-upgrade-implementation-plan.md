# 2026-06-16 Harness Workflow Upgrade Implementation Plan

## Plan Header

- Specification: `docs/specifications/2026-06-16-harness-workflow-upgrade-specification.md`
- Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`
- Scope summary: Add dynamic Harness workflow classes, require specs/plans to bind to them, encode P0/P1 article-derived principles, wire source/strategy/virtual-demand validation into release verification, and add the project instruction entrypoint.
- Out of scope:
  - Business runtime behavior changes.
  - CI provider migration.
  - Any AI-tool-specific mandatory gate.

## Change Steps

### Step 1: Add Workflow Classification Assets

- Files/modules:
  - `docs/harness-workflows.md`
  - `docs/harness-workflows.json`
  - `docs/harness-source-analysis.md`
- Behavior change:
  - Define reusable workflow classes for focused edits, spec-first features, wide refactors, deep verification, research synthesis, security review, incident triage, exploration tournaments, long-run task graphs, interactive artifacts, and skill evolution.
  - Trace P0/P1 sources and adopted principles in the manifest.
  - Record conflict decisions in source analysis.
- Verification:
  - `scripts/check_harness_workflows.sh`

### Step 2: Add Validator With Failing Tests First

- Files/modules:
  - `scripts/check_harness_workflows_test.sh`
  - `scripts/check_harness_workflows.sh`
- Behavior change:
  - Validate manifest structure, source traceability, principles, strategy fields, pattern vocabulary, quarantine consistency, evidence paths, tool-neutral verification commands, virtual demand coverage, and spec/plan workflow bindings.
- Verification:
  - `bash scripts/check_harness_workflows_test.sh`

### Step 3: Add Virtual Demand Coverage

- Files/modules:
  - `docs/harness-virtual-requirements.json`
- Behavior change:
  - Use synthetic demands to prove the framework covers small edits, API changes, refactors, claim verification, research, security, incidents, tournaments, long-running task graphs, interactive artifacts, and skill evolution.
- Verification:
  - `scripts/check_harness_workflows.sh`

### Step 4: Bind Existing Specs And Plans

- Files/modules:
  - `docs/specifications/*.md`
  - `docs/implementation-plans/*.md`
  - `docs/specifications/_template/harness.md`
- Behavior change:
  - Existing non-template specs and implementation plans explicitly declare their governing workflow class.
- Verification:
  - `scripts/check_harness_workflows.sh`

### Step 5: Wire Into Developer And Release Paths

- Files/modules:
  - `Makefile`
  - `scripts/verify_release.sh`
  - `AGENTS.md`
  - `CLAUDE.md`
  - `.ai-boundaries.yml`
  - `README.md`
- Behavior change:
  - `make check-harness-workflows` is available for focused validation.
  - `make verify-release` includes workflow validation and validator self-tests.
  - Project AI rules are read from one checked-in source.
- Verification:
  - `AI_BOUNDARY_APPROVED=1 make verify-release`

## Rollback

- Remove the workflow docs/manifest, validator scripts, spec/plan bindings, Make target, release gate entries, and instruction entrypoint.
- Rollback is docs/scripts-only and does not affect runtime data or API compatibility.
