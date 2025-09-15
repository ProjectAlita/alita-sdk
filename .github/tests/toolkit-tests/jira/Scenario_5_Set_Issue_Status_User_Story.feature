@jira @story @status @workflow @functional
Feature: Set workflow status on a User Story
  Users must be able to transition a Story to reflect its progress in the workflow.

  # Original Input Context (preserved)
  # Test name: Tool - Set Issue status
  # Test type: functional
  # Test Data:
  #   Jira ID: {{jira_id_for_update_scenarios}}
  #   Project ID: EL
  #   Status: "IN PROGRESS"

  Background:
    Given an existing Jira Story with key "{{jira_id_for_update_scenarios}}" in project "EL"
    And I am an authenticated Jira user with permission to transition issues

  Scenario: Successfully transition issue status
    When I transition the issue status to "IN PROGRESS"
    Then the issue status should be "IN PROGRESS"
    And I can retrieve the issue to confirm the status change

  # EXPECTED OUTPUT (preserved):
  # A confirmation message stating the status was set successfully and verified via retrieval.