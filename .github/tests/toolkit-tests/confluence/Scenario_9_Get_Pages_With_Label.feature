@confluence @page @label @search @functional
Feature: Get pages with a specific label
  The system must return pages that have a given label "testing" so users can filter content.

  # Original Input Context (preserved)
  # Test name: Tool - Get Pages with Label
  # Test type: functional
  # Test Data:
  #   Label: analytics
  #       ### Acceptance Criteria
  #         - Able to connect to Confluence API using token.
  #         - Pages with the label "testing" are returned.
  #         - Each returned page contains the requested label "testing".

  Background:
    Given I am an authenticated Confluence user with permission to view pages
    And the Confluence space key is "SD"

  Scenario: Successfully retrieve pages that have the label "testing"
    When I request pages with label "testing"
    Then the response should contain one or more pages
    And each page in the response should include the label "testing"

  # EXPECTED OUTPUT (preserved):
  # A list of pages that have the specified label; each page can be retrieved individually.
