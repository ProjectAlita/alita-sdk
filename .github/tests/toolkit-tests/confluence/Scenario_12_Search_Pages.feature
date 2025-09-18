@confluence @page @search @functional
Feature: Search Confluence pages by query
  The system must support searching pages by free-text query to find relevant content.

  # Original Input Context (preserved)
  # Test name: Tool - Search Pages
  # Test type: functional
  # Test Data:
  #   Query: "update"
  #       ### Acceptance Criteria
  #         - Able to connect to Confluence API using token.
  #         - Search returns pages relevant to the query "update".

  Background:
    Given I am an authenticated Confluence user with permission to view pages
    And the Confluence space key is "SD"

  Scenario: Successfully search pages using a free-text query
    When I search pages with query "update"
    Then the response should include pages whose title or content match the query "update"
    And the results should be ranked or relevant to the query "update"

  # EXPECTED OUTPUT (preserved):
  # A list of pages matching the query with relevance information where available.
