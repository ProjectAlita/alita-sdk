@confluence @page @label @list @functional
Feature: List pages with a label (paginated)
  The system must list pages having a specific label, supporting pagination and sorting.

  # Original Input Context (preserved)
  # Test name: Tool - List Pages with Label "testing"
  # Test type: functional
  # Test Data:
  #   Label: docs
  #   Start: 0
  #   Limit: 25
  #       ### Acceptance Criteria
  #         - Able to connect to Confluence API using token.
  #         - Paginated results are returned.
  #         - Each result contains the label "testing" requested.

  Background:
    Given I am an authenticated Confluence user with permission to view pages
    And the Confluence space key is "testing"

  Scenario: Successfully list pages with label "testing" with pagination
    When I request a list of pages with label "testing" starting at 0 with limit 25
    Then the response should include pagination metadata
    And each page in the current page of results should include the "testing" label

  # EXPECTED OUTPUT (preserved):
  # A paginated list of pages with the label, including total size and current page details.
