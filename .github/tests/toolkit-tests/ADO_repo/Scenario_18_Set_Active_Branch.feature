@ado @branch @set @active @functional
Feature: Set active branch in Azure DevOps repository
  The system must allow setting a specific branch as active for subsequent operations and workflow context.

  # Original Input Context (preserved)
  # Tool: set_active_branch
  # Test type: functional
  # Test Data:
  #   Repository Name: "27e65563-62b8-4834-9259-88bb56f47146"
  #   Branch Name: "{{base_branch}}"

  Background:
    Given I am an authenticated Azure DevOps user with repository access
    And the branch "{{base_branch}}" exists in the repository

  @positive @set-active-branch
  Scenario: User successfully sets active branch
    When I select the "set_active_branch" tool
    And I specify repository "27e65563-62b8-4834-9259-88bb56f47146"
    And I specify branch name "{{base_branch}}"
    And I click run
    Then the specified branch should be set as active
    And subsequent operations should use this branch context
    And the operation should complete successfully

  # EXPECTED OUTPUT (preserved):
  # Confirmation that the branch has been set as active, with branch name and repository context.
  # All future file operations will use this branch until changed.
