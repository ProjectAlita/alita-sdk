@bitbucket @pullrequest @changes @functional
Feature: Get pull request changes from Bitbucket repository
  The system must allow users to see file changes in pull requests so that code review can be conducted.

  # Original Input Context (preserved)
  # Test name: Tool - Get Pull Request Changes
  # Test type: functional
  # Test Data:
  #   Pull Request ID: {{pr_id}}

  Background:
    Given I am an authenticated Bitbucket user with repository access
    And a pull request with ID "{{pr_id}}" exists with file changes

  Scenario: Successfully retrieve pull request file changes
    When I get the file changes for pull request "{{pr_id}}"
    Then the file changes should be retrieved successfully
    And the response should contain a list of modified files
    And each file should show change type (added, modified, deleted)
    And each file should show number of additions and deletions
    And the changes should include at least one file as modified

  # EXPECTED OUTPUT (preserved):
  # A list of changed files with change statistics and modification types.
  # The agent should display the changes in a diff-like format for easy review.