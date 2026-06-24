# SPEC-CHAT-LANGUAGE-CONSISTENCY-001 Implementation Plan

Workflow Class: HARNESS-SPEC-FIRST-FEATURE

## Verification Command

```bash
.venv/bin/python -m pytest tests/test_chat_behavior_policy.py tests/test_agent_factory.py tests/test_chat_behavior_eval.py tests/test_orchestrator.py -q
PYTHON=.venv/bin/python AI_BOUNDARY_APPROVED=1 make verify-release
```

## Phase 1: Specify And Freeze Cases

1. Add language-consistency golden cases to `tests/chat_eval/golden_cases.jsonl`:
   - Chinese prompt with English product terms must stay Chinese.
   - English prompt must stay English.
   - Chinese prompt explicitly requesting English must answer English.
   - Output guardrail must classify high-confidence wrong-language output as
     `language_mismatch`.
2. Extend coverage summary with `language_mismatch`.

## Phase 2: Runtime Language Policy

1. Add `TargetLanguage` enum-like constants and deterministic detection helpers
   in `app/runtime/chat_behavior.py`.
2. Add `build_language_instruction(target_language)` for run-scoped
   instructions.
3. Update `DEFAULT_CHAT_BEHAVIOR_POLICY` answer principles so the static prompt
   explains the server-owned language policy.
4. Add `LANGUAGE_MISMATCH` to `GuardrailCategory`.

## Phase 3: Pydantic AI Integration

1. Extend `AgentDeps` with `target_language` and `language_instruction`.
2. Register `@agent.instructions` so each run sends the computed language
   instruction without modifying the persisted user message.
3. Add focused tests showing the instruction is present in the model request.

## Phase 4: Streaming Output Guardrail

1. Extend `StreamingOutputGuardrail` with optional `target_language`.
2. Add a prefix language gate before releasing early output:
   - Open gate when the target-language signal is present.
   - Refuse with localized safe response on high-confidence mismatch.
3. Keep the existing tail-window leak detection behavior after the language
   gate opens.
4. Pass target language from `AgentOrchestrator` into streaming and non-streaming
   output guardrails.

## Phase 5: Run Plan And Metadata Hygiene

1. Compute target language before `mark_running_with_plan`.
2. Add server-owned `target_language` to `_plan_snapshot`.
3. Strip client-supplied `target_language`, `language_policy`, and
   `disable_language_guardrail` from plan metadata.
4. Ensure deterministic input-refusal plans also record target language.

## Phase 6: Verification

1. Run focused tests.
2. Run full release verification.
3. Review `git diff` for accidental broad changes or secret exposure.

## Rollback

Revert this spec, implementation plan, language helper changes, test fixtures,
and orchestrator/agent_factory wiring. Existing v2 behavior policy and
non-language guardrails should continue to work independently.
