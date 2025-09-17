@ado @relations @types @get @functional
Feature: List available relation types in Azure DevOps
  The system must allow retrieval of relation types so linking semantics can be applied correctly.

  # Original Input Context (preserved)
  # Tool: Get relation types
  # Test type: functional

  Background:
    Given I am an authenticated ADO user with permission to view relation metadata

  Scenario: Successfully list work item relation types
    When I get the available work item relation types
    Then the response should include a collection of relation types
    And at least one relation type should have a reference name
    And the response should include a count of relation types

  # EXPECTED OUTPUT (preserved):
  # Array of relation type objects with name and reference metadata.