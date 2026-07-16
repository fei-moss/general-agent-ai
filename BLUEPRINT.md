# General Agent AI Harness Blueprint

This Blueprint maps the compact shared Harness architecture onto this mature Python service without replacing project-owned runtime, deployment, or verification contracts.

## Repository Map

| Layer | Source of truth | Mechanical proof |
| --- | --- | --- |
| Repository guidance | `AGENTS.md`, `.ai-boundaries.yml` | Boundary check and `CLAUDE.md` symlink gate |
| Task routing | `docs/harness-workflows.md` | Compact workflow manifest and registry gate |
| New governed behavior | `specs/<module>/spec.md` | `specs/index.json` and tests |
| Legacy governed behavior | `docs/specifications/`, `docs/implementation-plans/` | `scripts/check_spec_contract.sh` and tests |
| Runtime/deployment facts | Code, project docs, runbooks, `dockerhost/` | Project-native checks and smoke evidence |
| Release and sync safety | `harness/harness.lock`, `harness/harness_profiles.json`, `harness/scaffold_manifest.json` | Versioned `harnessctl` evidence and semantic comparison |

## AI Architecture Constitution

- `AGENTS.md` is a thin repository entrypoint; `CLAUDE.md` links to it.
- This Blueprint, project docs, runbooks, specs, tests, and configuration own unique facts, decisions, context, and evidence.
- Skills route to repository authority. Thin scripts wrap the pinned engine or implement project-specific custom gates.
- Relocate valid facts before slimming. Prompt, skill, and Harness maintenance is net-zero or net-negative; artifact growth must not duplicate authority.
- Do not manufacture specs, plans, skills, or ledgers for read-only diagnosis, bounded restoration, or Harness maintenance.

## Project Architecture Boundaries

- FastAPI owns transport, Pydantic AI owns one-run orchestration, Celery owns background execution, the event bus owns streaming/replay, and the DB layer owns persistence.
- Provider admission, quotas, settlement, retries, secret handling, durable state, and replay remain server-owned contracts outside Pydantic AI.
- DockerHost procedure lives in `docs/DOCKERHOST_RELEASE_RUNBOOK.md`; local credentials and machine instructions stay outside the repository.

## Safety And Verification

- `.ai-boundaries.yml` fails closed for unclassified, approval-required, or forbidden changes.
- `verify-change` checks the complete dirty development change against an explicit base.
- `verify-release` checks a clean candidate, runs the project-native release custom gate, and writes auditable evidence under `.artifacts/release/`.
- `harnessctl` is pinned by `harness/harness.lock`; engine code and engine tests do not live in this repository.
- The registry gate enforces the four workflow IDs, new-spec registry agreement, Harness line budget, and prompt/manifest/profile size budgets.

## Adoption Boundary

- Existing product specs and plans remain valid historical contracts; new governed work uses the consolidated `specs/<module>/spec.md` shape.
- Preserve project-native checks and unknown project-owned content during future refreshes.
- `docs/harness-adoption.md` owns semantic merge rules, and `harness/scaffold_manifest.json` records managed and retired surfaces.
