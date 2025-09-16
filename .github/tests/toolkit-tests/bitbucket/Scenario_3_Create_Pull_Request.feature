@bitbucket @pullrequest @create @functional
Feature: Create a new pull request in Bitbucket repository
  The system must allow creation of pull requests so that code changes can be reviewed before merging.

  # Original Input Context (preserved)
  # Test name: Tool - Create Pull Request
  # Test type: functional
  # Test Data:
  #   Source Branch: "{{branch_name}}"
  #   Target Branch: main
  #   Title: Add User Authentication Feature
  #   Description: Implementation of user authentication with login validation

  Background:
    Given I am an authenticated Bitbucket user with repository access
    And the branch "{{branch_name}}" has commits ahead of "main"

  Scenario: Successfully create a pull request
    When I create a pull request from "{{branch_name}}" to "main" with:
      | Title       | Add User Authentication Feature |
      | Description | Implementation of user authentication with login validation and error handling. This PR includes: - LoginManager class with authentication logic - Input validation and error handling - Unit tests for authentication methods |
    Then the pull request should be created successfully
    And the response should contain the pull request ID
    And the pull request should be in "OPEN" status
    And I can retrieve the pull request by its ID
    And the pull request title should be "Add User Authentication Feature"

  # EXPECTED OUTPUT (preserved):
  # A confirmation message stating the pull request was created successfully, including PR ID and URL.
  # The agent should verify this by retrieving the pull request details.