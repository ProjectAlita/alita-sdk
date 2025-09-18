@confluence @page @read @functional
Feature: Read a Confluence page by ID
  The system must allow reading page content and metadata by page ID so content can be displayed.

  # Original Input Context (preserved)
  # Test name: Tool - Read Page by ID "43679747"
  # Test type: functional
  # Test Data:
  #   Page id: "43679747"
  #       ### Acceptance Criteria
  #         - Able to connect to Confluence API using token.
  #         - Page content and metadata are returned.

  Background:
    Given I am an authenticated Confluence user with permission to view pages
    And the Confluence space key is "SD"

  Scenario: Successfully read a page by id "43679747"
    When I read the page with id "43679747"
    Then the response should contain the page id "43679747"
    And the response should include the page title and content
    And the content should contain expected text if present

  # EXPECTED OUTPUT (preserved):
  # Full page representation including id, title, body and metadata that can be used to render the page.
