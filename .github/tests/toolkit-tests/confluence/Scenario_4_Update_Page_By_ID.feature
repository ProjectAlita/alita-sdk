@confluence @page @update @functional
Feature: Update a Page by ID in Confluence
  The system must allow updating an existing Confluence page by its ID so content can be revised.

  # Original Input Context (preserved)
  # Test name: Tool - Update Page by ID
  # Test type: functional
  # Test Data:
  #   Page id: "49152001"
  #   New title: [Test] - Updated Page
  #   New content: Updated content
  #       ### Acceptance Criteria
  #         - Able to connect to Confluence API using token.
  #         - Page is updated and new content is stored.
  #         - Updated page can be retrieved and reflects changes.

  Background:
    Given I am an authenticated Confluence user with permission to edit pages
    And the Confluence space key is "SD"

  Scenario: Successfully update a Confluence page using its id
    When I update the page with id "49152001" to have title "[Test] - Updated Page" and content:
      """
      Updated content for the page.
      """
    Then the update should be successful
    And retrieving the page by id "49152001" should return the updated title
    And the page content should contain "Updated content for the page."

  # EXPECTED OUTPUT (preserved):
  # A confirmation message stating the page was updated successfully. Verification by retrieving the page and confirming updated fields.
