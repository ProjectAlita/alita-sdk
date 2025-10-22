@ado @stepback @search @index @advanced @functional
Feature: Perform stepback search on indexed data in Azure DevOps system
  The system must allow advanced stepback search for comprehensive information retrieval with broader context analysis.

  # Original Input Context (preserved)
  # Tool: stepback_search_index
  # Test type: functional
  # Test Data:
  #   Query: "{{query}}" - Search query text (required)
  #   Collection Suffix: "{{collection_suffix}}" (optional)

  Background:
    Given I am an authenticated Azure DevOps user with system access
    And there is indexed data available for stepback searching

  @positive @stepback-search-index
  Scenario: User successfully performs stepback search on indexed data
    When I select the "stepback_search_index" tool
    And I enter "{{query}}" in the Query field
    And I enter "{{collection_suffix}}" in the Collection suffix field
    And I click run
    Then I should see comprehensive search results with broader context
    And the results should include both direct and contextual matches
    And the operation should complete successfully

  # EXPECTED OUTPUT (preserved):
  # Enhanced search results with stepback analysis showing direct and contextual information
  # for comprehensive information retrieval with broader context within Azure DevOps workflows.
