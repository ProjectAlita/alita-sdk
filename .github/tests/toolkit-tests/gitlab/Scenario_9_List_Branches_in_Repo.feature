@gitlab @branches @list @functional
Feature: List all branches in a Gitlab repository
  The system must allow users to retrieve all branch names for collaboration and workflow management.

  # Original Input Context (preserved)
  # Test name: Tool - List Branches
  # Test type: functional
  # Test Data:
  #   Repository: hrachsg/toolkit-testing

  Background:
    Given I am an authenticated Gitlab user with access to the repository "hrachsg/toolkit-testing"

  Scenario: Successfully list all branches in the repository
    When I request the list of branches
    Then the response should include all branch names in the repository
    And the branch list should contain "master"
    And the branch list should contain any feature branches

  # EXPECTED OUTPUT (preserved):
  # A confirmation message stating the branch list was retrieved successfully, including all branch names.
