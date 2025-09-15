@jira @story @fields @functional
Feature: Retrieve specific field info of a User Story
  Users or automation must fetch only required fields (summary, description) for efficiency.

  # Original Input Context (preserved)
  # Test name: Tool - Get specific field info
  # Test type: functional
  # Test Data:
  #   Jira ID: {{jira_id_for_update_scenarios}}
  #   Project ID: EL
  #   Fields requested: Summary, Description

  Background:
    Given an existing Jira Story with key "{{jira_id_for_update_scenarios}}"
    And I am an authenticated Jira user

  Scenario: Successfully retrieve specific fields
    When I request the fields:
      | field       |
      | summary     |
      | description |
    Then the response should include the field "summary"
    And the response should include the field "description"
    And no unexpected large field set should be returned

  # EXPECTED OUTPUT (preserved):
  # Confirmation message that specific field info was retrieved successfully.