@gitlab @pr @changes @get @functional
Feature: Retrieve changes from a Gitlab pull request
  The system must allow users to view changes in pull requests for review and auditing.

  # Original Input Context (preserved)
  # Test name: Tool - Get PR Changes
  # Test type: functional
  # Test Data:
  #   PR Number: "{{pr_number}}"

  Background:
    Given a pull request exists with number "{{pr_number}}"

  Scenario: Successfully retrieve pull request changes
    When I request the list of changes in pull request "{{pr_number}}"
    Then I should see the files and lines modified in the pull request

  # EXPECTED OUTPUT (preserved):
  # A confirmation message stating the pull request changes were retrieved successfully, including change details.
