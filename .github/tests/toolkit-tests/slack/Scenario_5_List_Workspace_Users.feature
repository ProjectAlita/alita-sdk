@slack @list_workspace_users @list @functional
Feature: List users in the Slack workspace
  The system must allow retrieval of all users in the Slack workspace.

  # Original Input Context (preserved)
  # Test name: Tool - List Workspace Users
  # Test type: functional

  Background:
    Given I am an authenticated Slack user with permission to list workspace users

  Scenario: Successfully list workspace users
    When I request a list of all users in the workspace
    Then the response should include an array of user objects
    And each user object should include id, name, and email (when provided)
    And the list should include at least one known user

  # EXPECTED OUTPUT (preserved):
  # A full workspace user listing with expected metadata per user.