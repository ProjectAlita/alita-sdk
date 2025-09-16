@bitbucket @branch @switch @functional
Feature: Set active branch in Bitbucket repository
  The system must allow users to switch between branches so that different development contexts can be accessed.

  # Original Input Context (preserved)
  # Test name: Tool - Set Active Branch
  # Test type: functional
  # Test Data:
  #   Current Branch: main
  #   Target Branch: "{{branch_name}}"

  Background:
    Given I am an authenticated Bitbucket user with repository access
    And both "main" and "{{branch_name}}" branches exist
    And I am currently on "main" branch

  Scenario: Successfully switch to feature branch
    When I set the active branch to "{{branch_name}}"
    Then the branch should be switched successfully
    And the current active branch should be "{{branch_name}}"
    And I should be able to access files specific to this branch
    And the file listing should reflect the feature branch content

  # EXPECTED OUTPUT (preserved):
  # A confirmation message stating the active branch was changed successfully.
  # The agent should verify this by confirming the current branch context.