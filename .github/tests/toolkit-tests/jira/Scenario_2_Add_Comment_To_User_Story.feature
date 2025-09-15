@jira @story @comment @functional
Feature: Add a comment to an existing User Story
  The system must allow users to add comments to an existing Story to provide collaboration context.

  # Original Input Context (preserved)
  # Test name: Tool - Add Comment
  # Test type: functional
  # Test Data:
  #   Jira ID: {{jira_id_for_update_scenarios}}
  #   Project ID: EL
  #   Comment body: 'This a comment to existing User Story.'

  Background:
    Given an existing Jira Story with key "{{jira_id_for_update_scenarios}}" in project "EL"
    And I am an authenticated Jira user with permission to comment

  Scenario: Successfully add a comment to a Story
    When I add a comment with body "This a comment to existing User Story." to the issue
    Then the comment should be added successfully
    And the response should include a comment identifier
    And I can retrieve the comment by the issue key "{{jira_id_for_update_scenarios}}"
    And the comment body should equal "This a comment to existing User Story."

  # EXPECTED OUTPUT (preserved):
  # A confirmation message stating the comment was created successfully, including a Jira Link for User Story.
  # The agent should verify this by successfully retrieving the comment using the Jira ID.