@jira @story @links @retrieve @functional
Feature: Retrieve remote links of a User Story
  Stakeholders must view previously attached remote links for context.

  # Original Input Context (preserved)
  # Test name: Tool - Get remote links
  # Test type: functional
  # Test Data:
  #   Jira ID: {{jira_id_for_update_scenarios}}
  #   Project ID: EL

  Background:
    Given an existing Jira Story with key "{{jira_id_for_update_scenarios}}" that has remote links
    And I am an authenticated Jira user

  Scenario: Successfully retrieve remote links
    When I request the remote links for the issue
    Then the response should include at least one remote link
    And each link should have a linkText and url

  # EXPECTED OUTPUT (preserved):
  # Confirmation message that remote links were retrieved successfully and verified.