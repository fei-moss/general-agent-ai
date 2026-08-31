# Harness Scaffold Context

This context names the handoff between the canonical scaffold, a delivered repository, and the two independent Skills that operate on opposite sides of that handoff.

## Language

**Scaffold Source**:
The canonical `ai-first-go-template` repository root from which one Template Delivery begins.
_Avoid_: Template project, sync workspace, source checkout

**Target Repository**:
The repository receiving the Repository Contract and retaining ownership of its product facts and extensions.
_Avoid_: Consumer, downstream project, migrated repo

**Template Delivery**:
One explicit cold start or upgrade that begins in the Scaffold Source and ends after the Target Repository proves convergence.
_Avoid_: Sync session, adoption lifecycle, ongoing governance

**Repository Contract**:
The target-local instructions, workflows, profiles, gates, locks, and verification interfaces required for Daily Harness Work.
_Avoid_: Installed template, plugin state, copied methodology

**Daily Harness Work**:
Normal product, incident, maintenance, release, and deployment work performed after Template Delivery.
_Avoid_: Template sync, lifecycle governance

**Suite Conformance**:
Release evidence that exact Scaffold Source, Harness Template Sync, and Harness Driven Development revisions honor the same handoff contract.
_Avoid_: Runtime coordination, plugin dependency, lockstep release
