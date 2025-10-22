@ado @remove @index @functional
Feature: Remove indexed data from Azure DevOps system
  The system must allow removal of indexed data for cleanup, maintenance, and data management within workflows.

  # Original Input Context (preserved)
  # Tool: remove_index
  # Test type: functional
  # Test Data:
  #   Collection Suffix: "{{collection_suffix}}" (optional)

  Background:
    Given I am an authenticated Azure DevOps user with system access
    And there is indexed data available for removal

  @positive @remove-index
  Scenario: User successfully removes indexed data
    When I select the "remove_index" tool
    And I enter "{{collection_suffix}}" in the Collection suffix field
    And I click run
    Then the indexed data should be removed successfully
    And the specified collection should be cleaned up
    And the operation should complete successfully

  # EXPECTED OUTPUT (preserved):
  # Confirmation of successful index removal with collection details and cleanup summary
  # for effective data management and maintenance within Azure DevOps workflows.
