@slack @create_slack_channel @channel @create @functional
Feature: Create a new Slack channel
  The system must allow creation of a new channel in Slack so that teams can organise work.

  # Original Input Context (preserved)
  # Test name: Tool - Create Slack Channel
  # Test type: functional
  # Test Data:
  #   Channel name: {{channel_name}}
  #   Topic/Description: "Channel for integration tests"

  Background:
    Given I am an authenticated Slack user with permission to create channels
    And the workspace does not already contain a channel named {{channel_name}}

  Scenario: Successfully create a new Slack channel
    When I create a channel with the name {{channel_name}} and topic "Channel for integration tests"
    Then the channel should be created successfully
    And the response should include the channel id
    And I can verify the channel exists in the workspace by id
    And the channel name should be "{{channel_name}}
    And the channel topic should be "Channel for integration tests"

  # EXPECTED OUTPUT (preserved):
  # A confirmation message stating the channel was created successfully, including the new channel ID and metadata.