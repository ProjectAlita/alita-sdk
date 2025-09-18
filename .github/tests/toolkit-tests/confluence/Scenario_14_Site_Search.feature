@confluence @site @search @functional
Feature: Perform a site-wide search in Confluence
  The system must support site-wide searching across content types to locate relevant items.

  # Original Input Context (preserved)
  # Test name: Tool - Site Search
  # Test type: functional
  # Test Data:
  #   Query: "Update"
  #       ### Acceptance Criteria
  #         - Able to connect to Confluence API using token.
  #         - Search returns results across pages, blog posts, and attachments where applicable.

  Background:
    Given I am an authenticated Confluence user with permission to view site content
    And the Confluence space key is "SD

  Scenario: Successfully perform a site-wide search
    When I perform a site search with query "Update"
    Then the response should include items across supported content types
    And each returned item should be relevant to the query "Update"

  # EXPECTED OUTPUT (preserved):
  # A broad set of search results that can include pages, blog posts, and attachments relevant to the query "Update".
