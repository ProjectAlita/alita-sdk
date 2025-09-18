@confluence @page @batch-create @functional
Feature: Batch create pages in Confluence
  The system must allow creation of multiple Confluence pages in a single operation to improve efficiency.

  # Original Input Context (preserved)
  # Test name: Tool - Batch Create Pages
  # Test type: functional
  # Test Data:
  #   Space key: "SD"
  #   Pages:
  #     - Json file with thw following information
  #     - Title: [Test] - Page One; Content: Page One content
        - {"page1_name": "page1_content"}
  #     - Title: [Test] - Page Two; Content: Page Two content
        - {"page2_name": "page2_content"}
  #       ### Acceptance Criteria
  #         - Able to connect to Confluence API using token.
  #         - All pages are created and return individual Title and IDs.
  #         - Each page is retrievable by Title ID.

  Background:
    Given I am an authenticated Confluence user with permission to create pages
    And the Confluence space key is "SD"

  Scenario: Successfully batch create multiple Confluence pages
    When I batch create pages with the following data:
      | title                 | content             |
      | [Test] - Page One     | Page One content    |
      | [Test] - Page Two     | Page Two content    |
    Then the operation should succeed for all pages
    And the response should contain a list of new page title and ids
    And I can retrieve each newly created page by its title and id
    And each page title should match the input titles

  # EXPECTED OUTPUT (preserved):
  # A confirmation that all pages were created with their respective IDs and links. The agent verifies by retrieving each page.
