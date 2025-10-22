@ado @pull-request @comment @functional
Feature: Comment on pull request in Azure DevOps repository
  The system must allow adding comments to pull requests for automated communication, updates, and feedback in code review workflows.

  # Original Input Context (preserved)
  # Tool: comment_pull_request
  # Test type: functional
  # Test Data:
  #   Repository Name: "27e65563-62b8-4834-9259-88bb56f47146"
  #   Pull Request ID: "{{pull_request_id}}"
  #   Comment Text: "{{comment_text}}"

  Background:
    Given I am an authenticated Azure DevOps user with repository access
    And a pull request with ID "{{pull_request_id}}" exists in the repository

  @positive @comment-pull-request
  Scenario: User successfully adds comment to pull request
    When I select the "comment_pull_request" tool
    And I specify repository "27e65563-62b8-4834-9259-88bb56f47146"
    And I specify pull request ID "{{pull_request_id}}"
    And I enter comment text "{{comment_text}}"
    And I click run
    Then the comment should be added to the pull request successfully
    And the comment should be visible in the pull request discussion
    And the operation should complete successfully

  # EXPECTED OUTPUT (preserved):
  # Confirmation of successful comment addition with pull request reference and comment details
  # for automated feedback, communication, and code review workflow enhancement.
