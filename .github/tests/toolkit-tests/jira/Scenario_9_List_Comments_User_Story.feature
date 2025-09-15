@jira @story @comments @list @functional
Feature: List all comments of a User Story
  Users must be able to view all comments for collaboration history.

  # Original Input Context (preserved)
  # Test name: Tool - List comments
  # Test type: functional
  # Test Data:
  #   Jira ID: {{jira_id_for_update_scenarios}}
  #   Project ID: EL

  Background:
    Given an existing Jira Story with key "{{jira_id_for_update_scenarios}}" that has comments
    And I am an authenticated Jira user

  Scenario: Successfully list all comments
    When I request all comments for the issue
    Then the response should include a comments collection
    And each comment should include an author and body
    And the comment count should be >= 1

  # EXPECTED OUTPUT (preserved):
  # Confirmation message stating all comments were retrieved successfully.