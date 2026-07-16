# Production Deployment Contract

Spec ID: `SPEC-PLATFORM-MECHANISM-ABSORPTION-002`

This repository's production-like release path is DockerHost Git pull deployment. Runtime correctness, secret hygiene, rollback safety, and smoke evidence are required release artifacts.

## Required Preflight

- Run the release gate with the project virtualenv:
  - `AI_BOUNDARY_APPROVED=1 AI_BOUNDARY_APPROVAL_EVIDENCE=owner-request:<reference> VERIFY_COMPARE_REF=<base> PY=.venv/bin/python scripts/verify_release.sh`
- Validate the DockerHost adapter before deployment:
  - `envctl check-project --dir /Users/chris/AiProject/general-agent-ai`
  - `envctl validate-template --dir /Users/chris/AiProject/general-agent-ai/dockerhost`
- Secret scanning must run through `gitleaks` when installed. Any findings must be triaged as real, placeholder-only, or historical blocker before release.

## DockerHost Git Pull Deployment

- Deploy only from a pushed Git ref.
- Use `envctl up` or branch-space deploy with `--git-url`, `--git-ref`, and `--git-subdir dockerhost`.
- Runtime secrets must be injected by name with `--secret-env` or by file path with `--secret-file`.
- Never pass inline secret values through command arguments, docs, prompts, PRs, logs, or audit artifacts.

## Required Runtime Evidence

- `/healthz` returns healthy.
- `/readyz` returns ready and reports provider guardrails, key-pool state, Redis, DB, event bus, and reaper checks.
- `stream=false` smoke returns `422 STREAM_FALSE_NOT_SUPPORTED`.
- Accepted chat smoke returns an `agent_run_id`, `conversation_id`, `stream_url`, and terminal success through SSE smoke.
- Worker/reaper logs are checked through bounded, redacted queries only.

## Rollback And Cleanup

- Rollback uses a known previous pushed SHA and repeats the same health, ready, and SSE smoke evidence.
- If a release changes schema or persisted data shape, confirm backward compatibility before rollback.
- Disposable environments must be cleaned up with `envctl down` when no longer needed.

## Audit Boundary

- Audit artifacts may record command shapes, Git refs, environment names, service names, status codes, run ids, and redacted paths.
- Audit artifacts must not include provider keys, DockerHost tokens, raw Authorization headers, DB/Redis passwords, private keys, cookies, raw prompts with private user data, or unredacted production logs.
