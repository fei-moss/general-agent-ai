---
spec_id: SPEC-PRODUCTION-DEPLOYMENT-001
module: production_deployment
status: implemented
workflow_class: HARNESS-SPEC-FIRST-FEATURE
---

# Production Deployment Specification

## Specification

### Behavior

- `SPEC-PROD-DEPLOY-001`: The repository provides `docker-compose-prd.yml` as the Jenkins-managed production entrypoint. From `/data/general-agent-ai`, the supported command is `docker compose --env-file .env -f docker-compose-prd.yml up -d --build --remove-orphans`.
- `SPEC-PROD-DEPLOY-002`: The production compose starts stable `api`, `worker`, `reaper`, and one-shot `migrate` services. Only `api` publishes a host port, using `${APP_BIND_ADDR:?APP_BIND_ADDR is required}:${APP_PORT:-8080}:8080`.
- `SPEC-PROD-DEPLOY-003`: Jenkins renders the root `.env.example` into `.env`. The template covers every `Settings` environment field and every compose interpolation; sensitive values, private endpoints, and connection strings use same-name `${KEY}` placeholders.
- `SPEC-PROD-DEPLOY-004`: The production image build uses `dockerhost/Dockerfile` with the repository root as build context. Root `.dockerignore` excludes real environment files, Git data, caches, local worktrees, build output, and archives.
- `SPEC-PROD-DEPLOY-005`: Long-running services restart unless stopped, log through stdout/stderr with Docker log rotation, and the API has an HTTP healthcheck. Worker and reaper remain foreground processes.
- `SPEC-PROD-DEPLOY-006`: Production Postgres/pgvector and Redis are external dependencies supplied through `DB_URL`, `REDIS_URL`, `CELERY_BROKER_URL`, and `CELERY_RESULT_BACKEND`. Their provisioning, backup, retention, and rollback compatibility remain operations decisions; this repository does not invent a production storage topology.
- `SPEC-PROD-DEPLOY-007`: `docs/ops/production-deployment-contract.md` is the single repository source for the operations contract, and `AGENTS.md` points to it before any deployment-file change.
- This spec supersedes only the root-document location and formal-production role previously recorded by `SPEC-PLATFORM-MECHANISM-ABSORPTION-002`; its historical DockerHost work remains governed by the dev/test runbook.

### Invariants

- Existing `docker-compose.yml`, `dockerhost/compose.yaml`, `dockerhost/env.example`, `dockerhost/Dockerfile`, and `dockerhost/template.yaml` retain their dev/test behavior.
- A real `.env`, provider secret, database credential, token, private endpoint, private key, or production dump is never committed or copied into an image.
- Production mode is fail-closed: mock providers are disabled, provider-secret validation is strict, and provider rate-limit accounting does not fail open.
- No database, Redis, worker, reaper, or migration port is published to the host.
- The Jenkins-owned pipeline and production traffic/security-group choice stay outside this repository.

### Performance And Compatibility

- API healthcheck timing follows the operations contract: 10-second interval, 3-second timeout, 12 retries, and 20-second start period.
- Docker logs rotate at 100 MB with three retained files per service.
- Local setup continues to use a separate non-secret `env.local.example`; the root `.env.example` is reserved for Jenkins production rendering.

## Implementation Plan

1. Add failing contract tests for the required production assets, environment coverage, secret placeholders, host-port template, Docker context hygiene, AGENTS pointer, and release-gate integration.
2. Relocate the obsolete root deployment document into the required `docs/ops/` authority and update the checker without weakening the existing DockerHost runbook checks.
3. Add the independent production compose, Jenkins environment template, Docker ignore rules, and local-development environment template while leaving `dockerhost/` and local compose untouched.
4. Keep the repository guidance and AI-boundary surface net-zero while classifying the new operational files as approval-required.
5. Run focused tests, the production contract checker, compose rendering, dev/test compatibility checks, `verify-change`, and the project release checks.

## Closeout Evidence

- RED test: before implementation, `pytest tests/test_production_deployment_contract.py -q` exited 1 with 4 expected failures and 2 passes for the missing contract path, production compose, complete environment template, and ignore rules.
- Focused tests: the same file passes 6/6; `scripts/check_production_deployment_contract.py`, spec registry, legacy spec contract, rendered `docker compose config`, final image build, image import/.env exclusion smoke, and `git diff --check` pass.
- Owner approval: the request to prepare production deployment from the supplied operations contract authorizes the approval-required deployment, script, policy, and project-guidance changes in this spec.
- Compatibility: `git diff origin/Deploy -- dockerhost docker-compose.yml` is empty, proving the existing dev/test compose and DockerHost adapter were not modified.
- Change gate: approved `VERIFY_COMPARE_REF=origin/Deploy make verify-change` passed; evidence is under `.artifacts/change/`.
- Project release: `scripts/check_project_release.sh` passed DockerHost compatibility, production contract, observability, imports, chat eval, scorecard, full pytest, and gitleaks; evidence is `.artifacts/release/project_release_summary.json`.
- Clean-candidate Harness release: deferred until these uncommitted changes become a reviewable commit; the project-native release gate itself is green.
- Residual risk: operations must supply production endpoints, credentials, bind address, provider/model selection, backup policy, and rollback-compatible data infrastructure before deployment.
