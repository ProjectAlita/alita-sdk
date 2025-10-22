@ado @search @index @functional
Feature: Search indexed data in Azure DevOps system
  The system must allow searching of indexed data for information retrieval and content discovery within workflows.

  # Original Input Context (preserved)
  # Tool: search_index
  # Test type: functional
  # Test Data:
  #   Query: "{{query}}" - Search query text (required)
  #   Collection Suffix: "{{collection_suffix}}" (optional)

  Background:
    Given I am an authenticated Azure DevOps user with system access
    And there is indexed data available for searching

  @positive @search-index
  Scenario: User successfully searches indexed data
    When I select the "search_index" tool
    And I enter "{{query}}" in the Query field
    And I enter "{{collection_suffix}}" in the Collection suffix field
    And I click run
    Then I should see search results matching the query
    And the results should display relevant content with relevance scores
    And the operation should complete successfully

  # EXPECTED OUTPUT (preserved):
  # Relevant search results with content snippets, relevance scores, and source references
  # for effective information retrieval and content discovery within Azure DevOps workflows.
