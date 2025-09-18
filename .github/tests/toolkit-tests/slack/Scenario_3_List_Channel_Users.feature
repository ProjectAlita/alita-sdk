@slack @list_channel_users @list @functional
Feature: List users in a Slack channel
  The system must allow retrieval of all members of a specific Slack channel.

  # Original Input Context (preserved)
  # Test name: Tool - List Channel Users
  # Test type: functional
  # Test Data:
  #   Channel: {{channel_name}}

  Background:
    Given I am an authenticated Slack user with permission to view channel members
    And the channel {{channel_name}} exists and has members

  Scenario: Successfully list users in a channel
    When I request the list of users for channel {{channel_name}}
    Then the response should include an array of user objects
    And each user object should include id, display name, and email (if available)
    And the list should contain at least one user

  # EXPECTED OUTPUT (preserved):
  # A member list for the specified channel including user metadata.