# SPEC-CHAT-LANGUAGE-CONSISTENCY-001

Workflow Class: HARNESS-SPEC-FIRST-FEATURE

## Problem

Ask this Agent currently relies on one static prompt sentence to "follow the
user's language". Frontend has observed that real model responses sometimes
switch between English and Chinese. In a streaming chat UI this is visible to
users before any final-output-only validation can run.

The defect is not a frontend rendering issue. It is a runtime behavior-control
gap: target language is not detected per run, not recorded in the run plan, not
sent to the model as run-scoped instruction, and not checked while streaming.

## Research Summary

- OpenAI prompt engineering guidance says model output is non-deterministic and
  recommends production pinning plus tests/evaluation suites for prompt
  behavior as prompts and model versions change:
  https://developers.openai.com/api/docs/guides/prompt-engineering
- OpenAI guardrail guidance separates input, output, and tool guardrails; output
  guardrails are the right control for validating or redacting final output:
  https://developers.openai.com/api/docs/guides/agents/guardrails-approvals
- OpenAI Agents SDK docs state output guardrails run on final agent output. For
  streaming, this is too late to prevent already-emitted wrong-language tokens:
  https://openai.github.io/openai-agents-python/guardrails/
- Pydantic AI supports dynamic instructions evaluated at run time from
  dependencies, which fits this repo's `AgentDeps` design:
  https://pydantic.dev/docs/ai/core-concepts/agent/
- Microsoft Azure OpenAI prompt guidance also warns that prompt success does not
  automatically generalize and responses still need validation:
  https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/prompt-engineering

## Goals

- Detect the target answer language for each run from explicit user language
  requests first, then from the latest user message.
- Treat mixed Chinese + English product terms as Chinese when the user message
  contains CJK text.
- Add a run-scoped language instruction through Pydantic AI dynamic
  instructions rather than mutating the persisted user message.
- Add `target_language` to the server-owned run plan so production traces can
  be audited.
- Extend the existing streaming output guardrail with a prefix language gate so
  high-confidence wrong-language output is blocked before it reaches the
  frontend.
- Add golden cases and tests so language behavior becomes part of normal
  behavior tuning.

## Non-Goals

- No external language detection service or new runtime dependency in this
  iteration.
- No full translation layer or automatic second LLM repair pass.
- No change to public API request/response schemas.
- No weakening of existing hidden-instruction, secret, or safety guardrails.

## Language Policy

### Target Language Detection

1. If the latest user message explicitly asks for English, target language is
   `en`.
2. If the latest user message explicitly asks for Chinese or Simplified Chinese,
   target language is `zh-Hans`.
3. If the message contains CJK characters, target language is `zh-Hans`, even
   when it also includes product terms such as Agent, Mint, Redeem, PnL, AUM,
   Top Holders, or Live Activities.
4. If the message contains Latin letters and no CJK characters, target language
   is `en`.
5. Otherwise target language is `unknown`; the model should follow the latest
   user message and default to concise Simplified Chinese if ambiguous.

### Model Instruction

For `zh-Hans`, the runtime instruction must require Simplified Chinese for
sentences, explanations, and refusals. Product terms and field names may remain
English when they are user-facing labels.

For `en`, the runtime instruction must require English sentences,
explanations, and refusals. Product terms can remain as-is.

The instruction is server-owned. User/RAG/tool content must not disable or
shadow it.

### Streaming Guardrail

The output guardrail must keep the existing leak-detection tail window. In
addition, when target language is known:

- For `zh-Hans`, buffer the early answer until CJK text appears. If enough
  Latin output appears without CJK text, block the response and emit a Chinese
  safe response instead of the wrong-language prefix.
- For `en`, buffer the early answer until Latin text appears. If enough CJK
  output appears without Latin text, block the response and emit an English safe
  response instead of the wrong-language prefix.
- Once the language gate opens, continue using the existing leak-detection
  streaming release behavior.

This is a deterministic high-confidence guardrail, not a complete semantic
language classifier.

## Data Contract

Run plan gains one additive server-owned field:

```json
{
  "target_language": "zh-Hans"
}
```

Client metadata keys named `target_language`, `language_policy`, or
`disable_language_guardrail` must not shadow server-owned plan fields.

## Acceptance Criteria

- Chinese user message with English product terms produces `target_language:
  zh-Hans` and receives a Simplified Chinese runtime instruction.
- English user message produces `target_language: en` and receives an English
  runtime instruction.
- Explicit language override in the user message is honored.
- A Chinese-target run does not stream an all-English assistant answer; it emits
  a sanitized Chinese language-mismatch fallback and an output-guardrail event.
- A mixed Chinese answer that preserves product terms such as Agent, PnL, Mint,
  Redeem, and Top Holders is allowed.
- Golden cases cover Chinese, English, explicit override, and output mismatch.
- Focused pytest and release verification pass.

## Files

- `app/runtime/chat_behavior.py`: target-language detection, dynamic language
  instructions, output language guardrail.
- `app/runtime/agent_factory.py`: extend `AgentDeps` and register dynamic
  instructions.
- `app/runtime/orchestrator.py`: compute target language, pass through deps,
  record run-plan metadata, configure streaming guardrail.
- `tests/test_chat_behavior_policy.py`: deterministic language policy tests.
- `tests/test_agent_factory.py`: dynamic instruction smoke coverage.
- `tests/test_orchestrator.py`: run-plan and streaming mismatch coverage.
- `tests/chat_eval/golden_cases.jsonl`: language behavior golden cases.
- `tests/test_chat_behavior_eval.py`: coverage gates.

## Residual Risk

The v0 detector is intentionally deterministic. It will not perfectly classify
every multilingual prompt, but it covers the product's common Chinese/English
drift cases without adding latency or a new provider dependency. A future
iteration can add model-assisted language classification or pre-stream repair if
real production examples show the deterministic gate is too coarse.
