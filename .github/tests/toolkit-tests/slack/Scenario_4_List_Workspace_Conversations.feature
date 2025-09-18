@slack @list_workspace_conversations @list @functional
Feature: List conversations in the Slack workspace
  The system must allow listing all conversations (channels, private groups, DMs) in the workspace.

  # Original Input Context (preserved)
  # Test name: Tool - List Workspace Conversations
  # Test type: functional

  Background:
    Given I am an authenticated Slack user with permission to list workspace conversations

  Scenario: Successfully list workspace conversations
    When I request a list of conversations in the workspace
    Then the response should include a collection of conversation objects
    And each conversation should include id, name (when applicable), and type
    And one of the conversations should have the name  (if public)

  # EXPECTED OUTPUT (preserved):
  # A collection of workspace conversations including metadata for each conversation.