@ado @pull-request @create @functional
Feature: Create pull request in Azure DevOps repository
  The system must allow creation of pull requests for automated code contributions, feature integration, and streamlined code review processes.

  # Original Input Context (preserved)
  # Tool: create_pull_request
  # Test type: functional
  # Test Data:
  #   Repository Name: "{{repository_name}}"
  #   Source Branch: "{{source_branch}}"
  #   Target Branch: "{{target_branch}}"
  #   Title: "{{pr_title}}"
  #   Description: "{{pr_description}}"

  Background:
    Given I am an authenticated Azure DevOps user with repository write access
    And the source branch "{{source_branch}}" exists with changes
    And the target branch "{{target_branch}}" exists

  @positive @create-pull-request
  Scenario: User successfully creates a pull request
    When I select the "create_pull_request" tool
    And I specify repository "{{repository_name}}"
    And I specify source branch "{{source_branch}}"
    And I specify target branch "{{target_branch}}"
    And I enter title "{{pr_title}}"
    And I enter description "{{pr_description}}"
    And I click run
    Then a new pull request should be created successfully
    And the pull request should link the specified branches
    And the operation should complete successfully

  # EXPECTED OUTPUT (preserved):
  # Confirmation of successful pull request creation with PR ID, branch references, and URL
  # for automated code contribution, feature integration, and streamlined review workflows.
