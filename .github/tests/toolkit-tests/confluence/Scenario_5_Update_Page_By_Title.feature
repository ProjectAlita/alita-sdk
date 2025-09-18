@confluence @page @update @functional
Feature: Update a Page by Title in Confluence
  The system must allow updating an existing Confluence page by its title "Ping" when ID is not known.

  # Original Input Context (preserved)
  # Test name: Tool - Update Page by Title
  # Test type: functional
  # Test Data:
  #   Title: [Test] - Confluence Page
  #   New content: Content updated by title
  #       ### Acceptance Criteria
  #         - Able to connect to Confluence API using token.
  #         - Page is found by title "Ping" and updated randomly.
  #         - Updated content is retrievable.

  Background:
    Given I am an authenticated Confluence user with permission to edit pages
    And the Confluence space key is "SD"

  Scenario: Successfully update a Confluence page using its title "Ping"
    When I update the page with title "Ping" to have content:
      "Updated_content"
      Content updated by title "Ping".
      
    Then the update should be successful
    And I can retrieve the page by its title "Ping" and see the updated content
    And the page content should contain "Content updated by title."

  # EXPECTED OUTPUT (preserved):
  # A confirmation that the page found by title "Ping" was updated and verified by retrieval.
