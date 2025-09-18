@slack @send_message @message @functional
Feature: Send a message to a Slack conversation
  The system must allow sending messages to a Slack channel or conversation so teammates can receive notifications.

  # Original Input Context (preserved)
  # Test name: Tool - Send Message
  # Test type: functional
  # Test Data:
  #   Channel ID: {{channel_ID}}
  #   Message content: "Hello team, this is an automated test message."

  Background:
    Given I am an authenticated Slack user with permission to post messages
    And the channel  exists

  Scenario: Successfully send a message to a channel {{channel_ID}}
    When I send the message:
      """
      Hello team, this is an automated test message.
      """
    
    Then the message should be posted successfully
    And the response should include a message id or timestamp
    And I can read the message from channel using the returned id/timestamp
    And the message content should match the sent text
    And the message author should be my user id

  # EXPECTED OUTPUT (preserved):
  # Confirmation that the message was posted successfully with message id/ts, and verification by reading it back with matching content and author.