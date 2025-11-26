@artifacts @index @remove @functional
Feature: Remove indexed data from Artifacts system
  The system must allow removal of indexed documents so that outdated or unwanted content can be cleaned up.

  # Original Input Context (preserved)
  # Tool: Remove index
  # Test type: functional
  # Test Data:
  #   Collection_suffix: docs - Optional, user can select all suffixes or specific one (e.g. docs)

  Background:
    Given I am an authenticated user with Artifacts access
    And there are indexed documents available for removal

  @positive @remove-index
  Scenario: User successfully removes indexed data
    When I select the "Remove index" tool
    And I enter "docs" in the Collection suffix field
    And I click run
    Then I should see confirmation of index removal
    And the system should clean up the specified indexed documents
    And the operation should complete successfully

  # EXPECTED OUTPUT (preserved):
  # A confirmation message stating the document(s) were removed successfully with count details.
  # The agent should verify removal by attempting to search for the removed documents and confirming they're not found.