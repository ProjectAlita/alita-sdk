@confluence @page @tree @functional
Feature: Get page tree for a space or root page
  The system must return a hierarchical tree of pages so users can navigate structure.

  # Original Input Context (preserved)
  # Test name: Tool - Get Page Tree
  # Test type: functional
  # Test Data:
  #   Root page id: "66119"
  #       ### Acceptance Criteria
  #         - Able to connect to Confluence API using token.
  #         - Page tree is returned with parent-child relationships.

  Background:
    Given I am an authenticated Confluence user with permission to view pages
    And the Confluence space key is "SD"

  Scenario: Successfully retrieve the page tree from a root page
    When I request the page tree starting at root page id "66119"
    Then the response should include a hierarchical list of pages
    And child pages should reference their parent page ids "66119"

  # EXPECTED OUTPUT (preserved):
  # A page tree structure containing parent and children nodes that can be used to navigate the space.
