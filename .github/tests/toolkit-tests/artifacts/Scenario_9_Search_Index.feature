@artifacts @index @search @functional
Feature: Search indexed data in Artifacts system
  The system must allow searching of indexed data so that users can find relevant documents and information.

  # Original Input Context (preserved)
  # Tool: Search index
  # Test type: functional
  # Test Data:
  #   Query: {{Query}} - Query text to search in the index

  Background:
    Given I am an authenticated user with Artifacts access
    And there are indexed documents available for searching

  @positive @search-index
  Scenario: User successfully searches indexed data
    When I select the "Search index" tool
    And I enter "{{Query}}" in the Query field
    And I click run
    Then I should see search results matching the query
    And the system should display relevant documents with relevance scores
    And the operation should complete successfully

  # EXPECTED OUTPUT (preserved):
  # A list of search results with document IDs, titles, content snippets, and relevance scores.
  # The agent should display the results in a readable format with proper ranking.