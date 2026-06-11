Feature: Module behavior
  @SPEC-MODULE-001
  Scenario: Accepted command produces the expected durable state
    Given an authenticated user and a valid request
    When the command is accepted
    Then the durable state change is persisted
    And an observable event or metric is emitted
