# Harness Adoption

Use this contract when refreshing this mature repository from the shared scaffold. Target-owned facts and extensions remain authoritative; the scaffold manifest supplies the shared baseline.

## Classify Existing Prompt Content

Classify every rule in root instructions, nested instructions, prompts, and Skill entrypoints before slimming it:

| Class | Action |
| --- | --- |
| Project fact or contract | Move it to the owning spec, runbook, configuration, test, or project artifact; leave only a pointer at the prompt or Skill entrypoint. |
| Repeated shared methodology | Delete it after the template authority that replaces it is wired. |
| Mechanically checkable rule | Encode it once in a script, test, manifest, or release gate; prompts may point to that enforcement. |
| Unknown or ambiguous content | Preserve it as target-owned and stop before changing its semantics. |

In template `manual_merge` files, `template-invariant` marks shared scaffold policy and `domain example: <name>` marks replaceable domain guidance. Never copy a domain example as project policy without matching project evidence.

## Classify Existing AI Tool Surfaces

- AI command entrypoints keep only unique invocation syntax and pointers to repository authority.
- Hooks that enforce a mandatory rule must call a repository script or gate; convenience-only hooks stay optional and tool-specific.
- Other AI configuration preserves project facts and supported compatibility wiring, but not personal permissions, credentials, providers, plugin grants, or machine paths.
- Existing Skills keep triggers, authority pointers, compact workflow, and stop conditions; relocate project content before deleting duplicated Skill prose.

## Mature-Repository Compatibility

- Existing contracts in `docs/specifications/` and `docs/implementation-plans/` are legacy project authority and are not bulk-rewritten solely to match the scaffold layout.
- New governed work uses `specs/<module>/spec.md`; `specs/index.json` registers only that new layout.
- `scripts/check_spec_contract.sh` remains a project custom gate for legacy contracts, while the pinned engine owns the new spec registry and Harness budgets.

## Adoption Completion

Adoption is complete only when the minimum set in `harness/scaffold_manifest.json` is wired, not merely copied:

- `harness/harness.lock` pins the engine version used by the wrappers.
- Boundary, spec-registry, change, candidate, and release wrappers are reachable from the normal developer flow.
- `specs/index.json` exactly matches governed directories in the new layout, including an intentionally empty registry.
- Project-native release checks remain reachable through configured custom gates.

Resolve every `manual_merge` path semantically, preserve native checks and custom gates, and run focused project checks plus the proportional Harness gate.
