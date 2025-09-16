@bitbucket @pullrequest @get @functional
Feature: Get pull request details from Bitbucket repository
  The system must allow users to retrieve pull request details so that code reviews can be conducted.

  # Original Input Context (preserved)
  # Test name: Tool - Get Pull Request
  # Test type: functional
  # Test Data:
  #   Pull Request ID: {{pr_id}}

  Background:
    Given I am an authenticated Bitbucket user with repository access
    And a pull request with ID "{{pr_id}}" exists

  Scenario: Successfully retrieve pull request details
    When I get the pull request details for ID "{{pr_id}}"
    Then the pull request details should be retrieved successfully
    And the response should contain pull request metadata
    And the details should include source and target branches
    And the details should include pull request status
    And the details should include author information
    And the details should include creation and update timestamps

  # EXPECTED OUTPUT (preserved):
  # Complete pull request details including metadata, branch information, and status.
  # The agent should display the information in a structured, readable format.