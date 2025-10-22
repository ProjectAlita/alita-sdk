@ado @branch @list @functional
Feature: List all branches in Azure DevOps repository
  The system must allow users to retrieve all branches so that repository structure can be understood and managed.

  # Original Input Context (preserved)
  # Tool: list_branches
  # Test type: functional
  # Test Data:
  #   Repository Name: "{{repository_name}}"

  Background:
    Given I am an authenticated Azure DevOps user with repository access
    And multiple branches exist in the repository

  @positive @list-branches
  Scenario: User successfully lists all repository branches
    When I select the "list_branches" tool
    And I specify repository "{{repository_name}}"
    And I click run
    Then I should see a list of all available branches
    And each branch should display name and latest commit information
    And the operation should complete successfully

  # EXPECTED OUTPUT (preserved):
  # A list of all branches with their names, latest commit hashes, and last activity information.
  # The agent should display branch details in a readable format for branch management tasks.
