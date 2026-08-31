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
scripts/check_project_spec_contract.sh
scripts/check_project_release.sh
```

## Project Conventions

- `app/api/` contains FastAPI routes and request/response integration.
- `app/runtime/` contains Agent orchestration. Keep Pydantic AI scoped to single-run orchestration.
- `app/tasks/` contains Celery/background execution only.
- `app/bus/` owns event streaming and replay behavior.
- `app/db/` owns persistence setup and database access.
- New governed behavior uses one `specs/<module>/spec.md` for Specification, Implementation Plan, and Closeout Evidence; `specs/index.json` must match those modules exactly.
- Existing `docs/specifications/` and `docs/implementation-plans/` are retained legacy contracts and remain protected by `scripts/check_project_spec_contract.sh`.
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
- Release readiness is proven through `make verify-release`; the project-native checks it invokes are owned by `scripts/check_project_release.sh`.

## Harness Workflows

`docs/harness-workflows.md` owns task routing. Template Delivery starts at the canonical Scaffold Source; after `harness/repository_verification.py ready`, use Harness Driven Development. Branch handling follows `docs/branch-collaboration.md`.

## Mandatory Ops Reference

Before modifying Dockerfile, docker-compose files, `.env.example`, Jenkinsfile, deploy scripts, or production deployment behavior, read and follow `docs/ops/production-deployment-contract.md`. `docs/DOCKERHOST_RELEASE_RUNBOOK.md` remains the dev/test DockerHost procedure; keep private paths and credentials out of the repository.

## AI Boundaries

`.ai-boundaries.yml` is the mechanical source of truth. Docs, specs, and tests listed as allowed may be edited freely. Runtime, scripts, dependencies, CI, Harness policy, and project guidance require explicit owner approval. Forbidden paths and private credentials must never be changed or written.
