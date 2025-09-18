@confluence @page @create @functional
Feature: Create a new Page in Confluence
  The system must allow creation of a new Confluence page so that documentation can be stored and shared.

  # Original Input Context (preserved)
  # Test name: Tool - Create Page
  # Test type: functional
  # Test Data:
  #   Space key: "SD"
  #   Title: [Test] - Confluence Page
  #   Content:
  #     As a Documentation Owner, I want to create a Confluence page so team knowledge is centralized.
  #       ### Acceptance Criteria
  #         - Able to connect to Confluence API using token.
  #         - Page is created and retrievable by title and ID.
  #         - Page content is stored correctly.

  Background:
    Given I am an authenticated Confluence user with permission to create pages
    And the Confluence space key is "SD"

  Scenario: Successfully create a new Confluence page
    When I create a page with title "[Test] - Confluence Page" and Body:
      "newly created page"
      As a Documentation Owner, I want to create a Confluence page so team knowledge is centralized.
      ### Acceptance Criteria
      - Able to connect to Confluence API using token.
      - Page is created and retrievable by Title and ID.
      - Page content is stored correctly.
      """
    Then the page should be created successfully
    And the response should contain a new Confluence page with Title and id
    And I can retrieve the newly created page by its Title and id
    And the page title should be "[Test] - Confluence Page"
    And the page content should contain "Able to connect to Confluence API using token."

  # EXPECTED OUTPUT (preserved):
  # A confirmation message stating the Confluence page was created successfully, including a new Confluence page link.
  # The agent should verify this by successfully retrieving the page's details using the new page Title and ID.
