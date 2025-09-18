@slack @read_messages @messages @functional
Feature: Read messages from a Slack conversation
  The system must allow reading recent messages from a Slack channel or conversation.

  # Original Input Context (preserved)
  # Test name: Tool - Read Messages
  # Test type: functional
  # Test Data:
  #   Channel ID: {{channel_ID}}
  #   Expected message snippet: "Hello team"

  Background:
    Given I am an authenticated Slack user with permission to read messages
    And the channel "test-channel" exists and contains messages

  Scenario: Successfully read messages from a channel
    When I read messages from channel {{channel_ID}} with limit 50
    Then the response should include an ordered list of message objects
    And at least one message should contain the text "Hello team" (if present)
    And each message should include author id, timestamp, and text

  # EXPECTED OUTPUT (preserved):
  # A messages payload containing recent messages and verification of expected content and metadata.