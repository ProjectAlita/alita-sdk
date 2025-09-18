@confluence @page @delete @functional
Feature: Delete a Page in Confluence
  The system must allow deletion of a Confluence page so obsolete content can be removed.

  # Original Input Context (preserved)
  # Test name: Tool - Delete Page
  # Test type: functional
  # Test Data:
  #   Page id: "50167809"
  #       ### Acceptance Criteria
  #         - Able to connect to Confluence API using token.
  #         - Page is deleted and subsequent retrieval returns not found.
      Or
      Page title: "[Test] - Page Two"
  #       ### Acceptance Criteria
  #         - Able to connect to Confluence API using token.
  #         - Page is deleted and subsequent retrieval returns not found.

  Background:
    Given I am an authenticated Confluence user with permission to delete pages
    And the Confluence space key is "SD"

  Scenario: Successfully delete an existing Confluence page
    When I delete the page with id "50167809"
    Then the page should be deleted successfully
    And retrieving the page by id "50167809" should return not found
    When I delete the page with Page title: "[Test] - Page Two"
    Then the page should be deleted successfully
    And retrieving the page by "[Test] - Page Two" should return not found

  # EXPECTED OUTPUT (preserved):
  # A confirmation message stating the page was deleted successfully. Verification by attempting to retrieve the page and receiving a not-found response.
