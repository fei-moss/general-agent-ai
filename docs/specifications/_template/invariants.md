# Invariants

Spec ID: `SPEC-MODULE-001`

- Ownership is checked before data is read or streamed.
- State transitions are idempotent or explicitly rejected on retry.
- External side effects are traceable by `trace_id`.
- Accepted asynchronous work eventually reaches a terminal state or is recovered by a reaper.
