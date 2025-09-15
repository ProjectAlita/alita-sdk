@jira @story @links @functional
Feature: Add remote links to a User Story
  The system must allow attaching external or internal remote links to enrich issue context.

  # Original Input Context (preserved)
  # Test name: Tool - Link issues
  # Test type: functional
  # Test Data:
  #   Jira ID: {{jira_id_for_update_scenarios}}
  #   Project ID: EL
  #   Links JSON with two links

  Background:
    Given an existing Jira Story with key "{{jira_id_for_update_scenarios}}"
    And I am an authenticated Jira user with permission to manage remote links

  Scenario: Successfully add remote links
    When I add the following remote links:
      | linkText                 | url                                                     |
      | Remote link to Elitea    | https://dev.elitea.ai                                   |
      | Link to EL-1             | https://epamelitea.atlassian.net/browse/EL-1            |
    Then the remote links should be added successfully
    And I can retrieve the issue remote links
    And the remote links list should include "Remote link to Elitea"
    And the remote links list should include "Link to EL-1"

  # EXPECTED OUTPUT (preserved):
  # Confirmation message and verification by retrieving the issue's details.