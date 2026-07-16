# PROJECT CONTRACT

This repository is an async Agent execution platform. Runtime correctness, bounded provider usage, secret hygiene, durable state, and streaming behavior outrank convenience.

## Build And Test

```bash
make test
VERIFY_COMPARE_REF=<base> make verify-change
VERIFY_COMPARE_REF=<base> make verify-release
```

Direct project checks:

```bash
.venv/bin/python -m pytest -q
scripts/check_spec_contract.sh
scripts/check_project_release.sh
```

## Project Conventions

- `app/api/` contains FastAPI routes and request/response integration.
- `app/runtime/` contains Agent orchestration. Keep Pydantic AI scoped to single-run orchestration.
- `app/tasks/` contains Celery/background execution only.
- `app/bus/` owns event streaming and replay behavior.
- `app/db/` owns persistence setup and database access.
- New governed behavior uses one `specs/<module>/spec.md` for Specification, Implementation Plan, and Closeout Evidence; `specs/index.json` must match those modules exactly.
- Existing `docs/specifications/` and `docs/implementation-plans/` are retained legacy contracts and remain protected by `scripts/check_spec_contract.sh`.
- Logs and errors must not expose provider secrets, API keys, raw tokens, or private credentials.

## Runtime Boundaries

- Do not let Pydantic AI absorb gateway, queue, global rate-limit, persistence, distributed scheduling, or replay responsibilities.
- Do not bypass provider/model rate-limit guardrails for real providers.
- Do not fail open in production if usage settlement or provider admission cannot be recorded.
- Do not store real provider secrets in code, tests, logs, Redis, Postgres, events, release artifacts, or docs.
- Do not implement runtime, API, task, configuration, or persistence behavior from chat once a matching approved spec exists.
- Do not weaken release, boundary, or spec-contract gates to make local work easier.

## Testing Requirements

- New runtime behavior needs tests before implementation.
- API/streaming changes need owner/auth, idempotency, disconnect/replay, and error-path coverage.
- Provider-limit changes need quota, backoff, fail-closed, and usage-settlement tests.
- Secret-management changes need redaction and missing-secret tests.
- Release readiness is proven through `scripts/verify_release.sh`; the project-native checks it invokes are owned by `scripts/check_project_release.sh`.

## Harness Workflows

`BLUEPRINT.md` maps repository authority. `docs/harness-workflows.md` owns task routing, and `docs/harness-workflows.json` is its compact machine-readable registry.

- Use `HARNESS-FOCUSED-CHANGE` for bounded restoration or behavior-preserving refactors.
- Use `HARNESS-SPEC-FIRST-FEATURE` for new or intentionally changed semantics.
- Use `HARNESS-VERIFICATION-INCIDENT` for read-only diagnosis or independent verification; reroute before mutation.
- Use `HARNESS-MAINTENANCE` for Harness, skill, eval, template, or process maintenance; do not create self-referential product specs.
- Harness maintenance must be net-zero or net-negative across the maintained Harness surface.

## DockerHost

`docs/DOCKERHOST_RELEASE_RUNBOOK.md` owns project deployment, redeploy, rollback, smoke, cleanup, and secret-injection procedure. `dockerhost/` owns the adapter. Keep private machine paths and credentials outside the repository, deploy only pushed refs, and never print or inline secrets.

## AI Boundaries

`.ai-boundaries.yml` is the mechanical source of truth. Docs, specs, and tests listed as allowed may be edited freely. Runtime, scripts, dependencies, CI, Harness policy, and project guidance require explicit owner approval. Forbidden paths and private credentials must never be changed or written.
