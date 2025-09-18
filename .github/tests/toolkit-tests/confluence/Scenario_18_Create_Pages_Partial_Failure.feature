@confluence @page @batch-create @functional
Feature: Batch create pages with partial failure handling
  The system must handle partial failures when creating multiple pages in a batch and return per-item results.

  # Original Input Context (preserved)
  # Test name: Tool - Batch Create Pages (Partial Failure)
  # Test type: functional
  # Test Data:
  #   Space key: "SD"
  #   Pages:
  #     - Title: [Test] - Valid Page; Content: Valid content
  #     - Title: [Test] - Valid Page; Content: Missing title (should fail)
  #       ### Acceptance Criteria
  #         - Able to connect to Confluence API using token.
  #         - The response provides per-item success/failure info.
  #         - Successful items return ids and failed items return error details.

  Background:
    Given I am an authenticated Confluence user with permission to create pages
    And the Confluence space key is {{space}}

  Scenario: Batch create pages where one item fails validation
    When I batch create pages with the following data:
      | title                 | content             |
      | [Test] - Valid Page   | Valid content       |
      |                      | Missing title       |
    Then the response should indicate one successful creation and one failure
    And the successful item should include a new page id
    And the failed item should include a descriptive error about missing title

  # EXPECTED OUTPUT (preserved):
  # A detailed per-item result indicating successes and failures, allowing the agent to report which pages were created and which failed and why.
