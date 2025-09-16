@bitbucket @pullrequest @comment @functional
Feature: Add comment to pull request in Bitbucket repository
  The system must allow users to add comments to pull requests so that code review collaboration can occur.

  # Original Input Context (preserved)
  # Test name: Tool - Add Pull Request Comment
  # Test type: functional
  # Test Data:
  #   Pull Request ID: {{pr_id}}
  #   Comment: This implementation looks good! Please add unit tests for the error handling scenarios.

  Background:
    Given I am an authenticated Bitbucket user with repository access
    And a pull request with ID "{{pr_id}}" exists

  Scenario: Successfully add comment to pull request
    When I add a comment to pull request "{{pr_id}}" with text:
      """
      This implementation looks good! Please add unit tests for the error handling scenarios.
      
      """
    Then the comment should be added successfully
    And the response should contain the comment ID
    And I can retrieve the pull request and see the new comment
    And the comment should be associated with my user account

  # EXPECTED OUTPUT (preserved):
  # A confirmation message stating the comment was added successfully, including comment ID.
  # The agent should verify this by retrieving the pull request and confirming the comment exists.