@bitbucket @branch @create @functional
Feature: Create a new branch in Bitbucket repository
  The system must allow creation of new branches so that development work can be isolated and managed.

  # Original Input Context (preserved)
  # Test name: Tool - Create Branch
  # Test type: functional
  # Test Data:
  #   Source Branch: main
  #   New Branch Name: "{{branch_name}}"
  #   Description: Feature branch for "Create branch" tool testing

  Background:
    Given I am an authenticated Bitbucket user with repository access
    And the source branch "main" exists

  Scenario: Successfully create a new feature branch
    When I create a new branch "{{branch_name}}" from source branch "main"
    Then the branch should be created successfully
    And the response should contain the new branch reference
    And I can retrieve the branch in the repository branch list
    And the branch should point to the same commit as "main"

  # EXPECTED OUTPUT (preserved):
  # A confirmation message stating the branch was created successfully, including the branch name and commit hash.
  # The agent should verify this by successfully listing branches and confirming the new branch exists.