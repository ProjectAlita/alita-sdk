@confluence @page @batch-update @functional
Feature: Batch update multiple Confluence pages
  The system must allow updating multiple pages in a single operation for efficiency.

  # Original Input Context (preserved)
  # Test name: Tool - Batch Update Pages
  # Test type: functional
  # Test Data:
  # List of ids of pages to be updated
  # List of new contents for each page. If content the same for all the pages then it should be a list with a single entry
  #   Updates:
  #     - id: "66119" ; title: [Test] - Page One Updated; content: New content one
  #     - id: "131589"; title: [Test] - Page Two Updated; content: New content two
  #       ### Acceptance Criteria
  #         - Able to connect to Confluence API using token.
  #         - All specified pages are updated successfully.
  #         - Each updated page is retrievable and reflects changes.

  Background:
    Given I am an authenticated Confluence user with permission to edit pages
    And the Confluence space key is "SD"

  Scenario: Successfully batch update multiple pages
    When I submit batch updates:
      | id  | title                        | content           |
      | "66119" | [Test] - Page One Updated    | New content one   |
      | "131589" | [Test] - Page Two Updated    | New content two   |
    Then the operation should succeed for all updates
    And each page should reflect its corresponding updates when retrieved

  # EXPECTED OUTPUT (preserved):
  # A confirmation that all updates were applied with verification via retrieval of updated pages.
