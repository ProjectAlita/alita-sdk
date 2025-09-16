@bitbucket @pullrequest @commits @functional
Feature: Get pull request commits from Bitbucket repository
  The system must allow users to see commit history in pull requests so that development progress can be tracked.

  # Original Input Context (preserved)
  # Test name: Tool - Get Pull Request Commits
  # Test type: functional
  # Test Data:
  #   Pull Request ID: {{pr_id}}

  Background:
    Given I am an authenticated Bitbucket user with repository access
    And a pull request with ID "{{pr_id}}" exists with multiple commits

  Scenario: Successfully retrieve pull request commits
    When I get the commits for pull request "{{pr_id}}"
    Then the commit history should be retrieved successfully
    And the response should contain a list of commits
    And each commit should have commit hash, message, and author
    And each commit should have timestamp information
    And the commits should be ordered chronologically

  # EXPECTED OUTPUT (preserved):
  # A chronological list of commits with their metadata and messages.
  # The agent should display the commit history in a readable timeline format.