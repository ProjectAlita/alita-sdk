@jira @story @labels @functional
Feature: Modify labels of an existing User Story
  Project stakeholders need to apply or adjust labels for classification and reporting.

  # Original Input Context (preserved)
  # Test name: Tool - Modify labels
  # Test type: functional
  # Test Data:
  #   Jira ID: {{jira_id_for_update_scenarios}}
  #   Project ID: EL
  #   Labels: "Elitea_AI_Generated", "Reviewed_US"

  Background:
    Given an existing Jira Story with key "{{jira_id_for_update_scenarios}}"
    And I am an authenticated Jira user with permission to edit issues

  Scenario: Successfully update labels
    When I set the labels to:
      | label               |
      | Elitea_AI_Generated |
      | Reviewed_US         |
    Then the issue should be updated successfully
    And I can retrieve the issue
    And the labels should include "Elitea_AI_Generated"
    And the labels should include "Reviewed_US"

  # EXPECTED OUTPUT (preserved):
  # A confirmation message stating the labels were updated successfully; verified by retrieving issue details.