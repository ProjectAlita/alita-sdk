@slack @invite_to_conversation @invite @functional
Feature: Invite a user to a Slack conversation
  The system must allow inviting a user to an existing Slack conversation so collaborators can join.

  # Original Input Context (preserved)
  # Test name: Tool - Invite to Conversation
  # Test type: functional
  # Test Data:
  #   Channel: {{channel_name}}
  #   Invitee ID: "D095W8NHED9"

  Background:
    Given I am an authenticated Slack user with permission to invite members
    And the channel {{channel_name}} exists

  Scenario: Successfully invite a user to a conversation
    When I invite the user with ID "D095W8NHED9" to the conversation {{channel_name}}
    Then the invite should be accepted by the API
    And the response should include the invited user's id and membership state
    And I can verify the user is a member of {{channel_name}}

  # EXPECTED OUTPUT (preserved):
  # A confirmation that the invitation succeeded and membership verification for the invited user.