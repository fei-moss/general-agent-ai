Feature: Harness workflow classification
  @SPEC-HARNESS-WORKFLOW-001
  Scenario: Classify a task before selecting an execution shape
    Given a task that may be handled by an AI tool
    When the task is release-sensitive, broad, adversarial, repetitive, runtime-dependent, or evidence-heavy
    Then the task is mapped to a documented HARNESS-* workflow class
    And the workflow class declares its source IDs and principle IDs
    And the workflow class declares its isolation model
    And the workflow class declares its verification rubric
    And the workflow class declares stop conditions

  @SPEC-HARNESS-WORKFLOW-001
  Scenario: Preserve the release harness as the hard gate
    Given a dynamic workflow has produced code, docs, specs, prompts, scripts, or migrations
    When the change is prepared for release
    Then the repository release harness remains the final verification authority
    And workflow evidence is written under .artifacts/
    And approval-required paths still require owner approval

  @SPEC-HARNESS-WORKFLOW-001
  Scenario: Preserve official source traceability
    Given a HARNESS-* workflow class is defined
    When the workflow manifest is validated
    Then the workflow class declares source_ids from the official source set
    And the workflow class declares adopted principle_ids
    And the source IDs and principle IDs are documented in the source analysis

  @SPEC-HARNESS-WORKFLOW-001
  Scenario: Quarantine untrusted inputs
    Given a workflow reads public issues, tickets, resumes, incidents, logs, web pages, or user-provided files
    When agents classify or summarize that untrusted content
    Then those agents do not perform high-privilege write actions
    And a separate acting agent or human performs privileged changes after review

  @SPEC-HARNESS-WORKFLOW-001
  Scenario: Verify runtime legibility
    Given a workflow changes startup, local development, UI feedback, observability, logs, metrics, traces, or smoke paths
    When the workflow uses HARNESS-RUNTIME-LEGIBILITY
    Then an agent can discover how to start and inspect the running system
    And runtime evidence is captured or the blocker is explicit

  @SPEC-HARNESS-WORKFLOW-001
  Scenario: Turn repeated failures into durable checks
    Given an agent, prompt, skill, review, or workflow failure repeats
    When the workflow uses HARNESS-EVAL-IMPROVEMENT-LOOP
    Then the failure is captured as an example or regression class
    And the improvement becomes an eval, test, hook, script, skill, or documented reviewer check
