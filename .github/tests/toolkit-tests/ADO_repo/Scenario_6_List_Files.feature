@ado @files @list @functional
Feature: List files in active branch of Azure DevOps repository
  The system must allow users to browse repository contents and view file structures for navigation and analysis.

  # Original Input Context (preserved)
  # Tool: list_files
  # Test type: functional
  # Test Data:
  #   Repository Name: "{{repository_name}}"
  #   Active Branch: Current active branch context

  Background:
    Given I am an authenticated Azure DevOps user with repository access
    And an active branch is set in the repository
    And files exist in the active branch

  @positive @list-files
  Scenario: User successfully lists files in active branch
    When I select the "list_files" tool
    And I specify repository "{{repository_name}}"
    And I click run
    Then I should see a list of all files in the active branch
    And each file should display path and basic information
    And the operation should complete successfully

  # EXPECTED OUTPUT (preserved):
  # A comprehensive list of files in the active branch with file paths, sizes, and last modification details.
  # The agent should present files in a structured, navigable format.
