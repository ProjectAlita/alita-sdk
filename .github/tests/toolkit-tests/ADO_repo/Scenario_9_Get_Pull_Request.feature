@ado @pull-request @get @functional
Feature: Get pull request details from Azure DevOps repository
  The system must allow retrieval of detailed pull request information for code review assistance and workflow integration.

  # Original Input Context (preserved)
  # Tool: get_pull_request
  # Test type: functional
  # Test Data:
  #   Repository Name: "27e65563-62b8-4834-9259-88bb56f47146"
  #   Pull Request ID: "{{pull_request_id}}"

  Background:
    Given I am an authenticated Azure DevOps user with repository access
    And a pull request with ID "{{pull_request_id}}" exists in the repository

  @positive @get-pull-request
  Scenario: User successfully retrieves pull request details
    When I select the "get_pull_request" tool
    And I specify repository "27e65563-62b8-4834-9259-88bb56f47146"
    And I specify pull request ID "{{pull_request_id}}"
    And I click run
    Then I should see detailed pull request information
    And the details should include title, description, status, and reviewers
    And the operation should complete successfully

  # EXPECTED OUTPUT (preserved):
  # Comprehensive pull request details including title, description, source/target branches, status, 
  # reviewers, and any associated comments for code review context.
