@ado @branch @create @functional
Feature: Create new branch in Azure DevOps repository
  The system must allow creation of new branches for feature development, bug fixes, and experimental changes.

  # Original Input Context (preserved)
  # Tool: create_branch
  # Test type: functional
  # Test Data:
  #   Repository Name: "27e65563-62b8-4834-9259-88bb56f47146"
  #   New Branch Name: "{{new_branch_name}}"
  #   Base Branch: "{{base_branch}}"

  Background:
    Given I am an authenticated Azure DevOps user with repository write access
    And the base branch "{{base_branch}}" exists in the repository

  @positive @create-branch
  Scenario: User successfully creates a new branch
    When I select the "create_branch" tool
    And I specify repository "27e65563-62b8-4834-9259-88bb56f47146"
    And I specify new branch name "{{new_branch_name}}"
    And I specify base branch "{{base_branch}}"
    And I click run
    Then a new branch should be created successfully
    And the branch should be based on the specified base branch
    And the operation should complete successfully

  # EXPECTED OUTPUT (preserved):
  # Confirmation of successful branch creation with branch name, base branch reference,
  # and commit hash for automated feature development workflow initiation.
