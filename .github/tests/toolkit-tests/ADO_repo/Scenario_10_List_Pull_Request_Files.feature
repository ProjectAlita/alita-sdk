@ado @pull-request @files @list @functional
Feature: List files changed in Azure DevOps pull request
  The system must allow retrieval of files changed in a pull request for code review analysis and change scope assessment.

  # Original Input Context (preserved)
  # Tool: list_pull_request_files
  # Test type: functional
  # Test Data:
  #   Repository Name: "{{repository_name}}"
  #   Pull Request ID: "{{pull_request_id}}"

  Background:
    Given I am an authenticated Azure DevOps user with repository access
    And a pull request with ID "{{pull_request_id}}" exists
    And the pull request contains file changes

  @positive @list-pull-request-files
  Scenario: User successfully lists pull request file changes
    When I select the "list_pull_request_files" tool
    And I specify repository "{{repository_name}}"
    And I specify pull request ID "{{pull_request_id}}"
    And I click run
    Then I should see a list of all changed files in the pull request
    And each file should show change type (added, modified, deleted)
    And the operation should complete successfully

  # EXPECTED OUTPUT (preserved):
  # A detailed list of files modified in the pull request with change types, file paths,
  # and modification summaries for comprehensive code review preparation.
