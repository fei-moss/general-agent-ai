# Harness Workflows

This file owns task routing and profile semantics. `docs/harness-workflows.json` contains only machine-readable class IDs; `harness/check_policy_projections.py` keeps entry files as checked projections.

## Route By Semantic Intent

| Workflow class | Use when | Artifact |
| --- | --- | --- |
| `HARNESS-VERIFICATION-INCIDENT` | Read-only diagnosis, incident triage, review, or claim verification | Findings and existing evidence; reroute before mutation |
| `HARNESS-FOCUSED-CHANGE` | Exact bounded correction or behavior-preserving refactor with known truth, including approved dev configuration | Focused checklist only when useful; no Specification |
| `HARNESS-SPEC-FIRST-FEATURE` | New or intentionally changed product semantics, or unresolved contract ambiguity | One `specs/<module>/spec.md` containing specification, plan, and closeout |
| `HARNESS-MAINTENANCE` | Harness, Skill, eval, template, or process upkeep | Existing maintenance contract or concise checklist; never a self-Spec |

Approval, protected paths, security relevance, deployment, and file type are independent controls; they do not choose the workflow. Non-trivial work keeps `workflow_class`, `target_truth`, and `stop_condition` in chat or an owning project artifact. `active_spec` exists only for Spec-first work.

## Verify Proportionally

| Profile | Use |
| --- | --- |
| `change` | Dirty development feedback and changed-path gates |
| `pull_request` | Clean review candidate and candidate-required gates |
| `release` | Final promotion or scheduled full verification |

Profiles are not workflows. Deployment alone selects neither Spec-first nor release. Run a required full release once per exact final SHA; reuse only evidence accepted by `harnessctl evidence verify`.

Repository instructions, approved specs, contracts, tests, runbooks, `.ai-boundaries.yml`, and branch rules remain authoritative. Stop on ambiguity, missing approval, untrusted privileged input, or a failed gate. After Template Delivery, Harness maintenance must remain net-line non-positive; an owner-approved initial bootstrap uses the engine's [recorded delivery classification](https://github.com/Fueav/harnessctl/blob/v0.5.1/README.md#workflow-registry-compatibility).
