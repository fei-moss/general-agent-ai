# 2026-06-29 World Cup Chat Server Migration Implementation Plan

- Specification: `SPEC-WORLDCUP-CHAT-SERVER-MIGRATION-001`
- Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`
- Target branch/baseline: local new project at `/Users/chris/AiProject/world-cup-chat-server`, copied from `/Users/chris/AiProject/general-agent-ai`.
- Scope summary: migrate the reusable async Chat Server platform, replace source-project business identity with World Cup forecasting behavior, keep Harness and DockerHost deployability, and prove the result through local gates plus DockerHost smoke.
- Out of scope: real Polymarket order execution, live market-data crawler, production auth, and large-scale load claims.

## Change Steps

1. Platform copy and baseline
   - Files/modules: full project tree excluding `.git`, `.venv`, `.artifacts`, caches.
   - Behavior change: create an independent sibling repository.
   - Data contract impact: none.
   - Tests to add/update: none.
   - Verification command: `git status --short`.
   - Rollback or compatibility note: delete the sibling directory if migration is abandoned.

2. World Cup behavior policy
   - Files/modules: `app/runtime/chat_behavior.py`, `app/runtime/agent_factory.py`.
   - Behavior change: replace Ask this Agent identity with World Cup match forecasting identity, evidence-led answer principles, Polymarket/no-bet constraints, and no direct-order behavior.
   - Data contract impact: none.
   - Tests to add/update: `tests/test_chat_behavior_policy.py`, `tests/test_agent_factory.py`.
   - Verification command: `.venv/bin/python -m pytest tests/test_chat_behavior_policy.py tests/test_agent_factory.py -q`.
   - Rollback or compatibility note: revert policy files without touching API/db/stream architecture.

3. Golden cases and seed knowledge
   - Files/modules: `tests/chat_eval/golden_cases.jsonl`, `tests/chat_eval/judge.py`, `scripts/sample_knowledge.json`.
   - Behavior change: remove active MOSS/Agent-detail fixtures and add World Cup forecasting cases.
   - Data contract impact: RAG seed content changes only.
   - Tests to add/update: `tests/test_chat_behavior_eval.py`.
   - Verification command: `.venv/bin/python -m pytest tests/test_chat_behavior_eval.py -q`.
   - Rollback or compatibility note: keep generic RAG framework tests; do not restore MOSS as default product data.

4. Project identity and DockerHost metadata
   - Files/modules: `AGENTS.md`, `README.md`, `docs/API.md`, `docs/INTEGRATION_GUIDE.md`, `docs/DOCKERHOST_RELEASE_RUNBOOK.md`, `dockerhost/template.yaml`, `dockerhost/env.example`, `app/api/main.py`, `tests/test_dockerhost_release_cli.py`.
   - Behavior change: new project name and Git/DockerHost environment examples.
   - Data contract impact: none.
   - Tests to add/update: DockerHost release CLI tests.
   - Verification command: `.venv/bin/python -m pytest tests/test_dockerhost_release_cli.py -q`.
   - Rollback or compatibility note: source service URLs and env names must not remain as active defaults.

5. Harness and release verification
   - Files/modules: specs/plans and release scripts unchanged except project docs.
   - Behavior change: no Harness weakening.
   - Data contract impact: none.
   - Tests to add/update: no new workflow class needed.
   - Verification command: `AI_BOUNDARY_APPROVED=1 SPEC_CONTRACT_APPROVED=1 make verify-release`.
   - Rollback or compatibility note: approval env vars acknowledge the user-requested runtime/config migration, not a gate bypass for failures.

6. DockerHost live smoke
   - Files/modules: `scripts/dockerhost_release.py`, DockerHost template/compose.
   - Behavior change: deploy new project from pushed Git ref and verify health plus async chat streaming.
   - Data contract impact: new remote environment only.
   - Tests to add/update: smoke transcript artifact.
   - Verification command:
     - `envctl check-project --dir /Users/chris/AiProject/world-cup-chat-server`
     - `envctl validate-template --dir /Users/chris/AiProject/world-cup-chat-server/dockerhost`
     - `scripts/dockerhost_release.py deploy ... --execute --audit-json .artifacts/release/worldcup_dockerhost_deploy_audit.json`
   - Rollback or compatibility note: `envctl down --name <env>` cleans disposable environment.

## Risk Controls

- Public contract risks: preserve `/chat`, stream, runs, conversations, and RAG API shapes.
- Money/accounting/security risks: no default direct-order or account-data access; keep provider and secret guardrails.
- Migration/rebuild risks: new DB starts empty; no source production data migration.
- Performance risks: do not claim new concurrency capacity beyond existing smoke/release evidence.
- Deployment/test-branch risks: DockerHost requires a pushed Git ref; remote creation/push must be verified before deploy.
- Unrelated local changes to avoid: source `/Users/chris/AiProject/general-agent-ai` remains untouched.

## Completion Criteria

- All planned files changed or explicitly deferred.
- Specification still matches implementation.
- Focused tests pass.
- Required harness gates pass or a concrete blocker is reported.
- DockerHost project validation passes.
- DockerHost live smoke reaches `RUN_COMPLETED` for a World Cup prompt.
- Review findings are fixed or explicitly accepted.
