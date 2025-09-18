@confluence @page @id @lookup @functional
Feature: Get page ID by title
  The system must return a page's ID when given its title to allow downstream operations when ID is unknown.

  # Original Input Context (preserved)
  # Test name: Tool - Get Page ID by Title
  # Test type: functional
  # Test Data:
  #   Title: [Test] - Confluence Page
  #       ### Acceptance Criteria
  #         - Able to connect to Confluence API using token.
  #         - The correct page id is returned for the given title.

  Background:
    Given I am an authenticated Confluence user with permission to view pages
    And the Confluence space key is "SD"

  Scenario: Successfully retrieve a page id by title
    When I request the id for page with title "[Test] - Confluence Page"
    Then the response should include a valid page id
    And I can use that id to retrieve the page

  # EXPECTED OUTPUT (preserved):
  # The numeric or string id of the page that matches the provided title; verified by retrieval.
