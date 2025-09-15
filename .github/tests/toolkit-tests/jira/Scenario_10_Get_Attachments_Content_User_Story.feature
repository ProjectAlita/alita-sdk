@jira @story @attachments @functional
Feature: Retrieve attachments content of a User Story
  The system must allow extraction of attachment metadata and content for analysis.

  # Original Input Context (preserved)
  # Test name: Tool - Get attachments content
  # Test type: functional
  # Test Data:
  #   Jira ID: {{jira_id_for_update_scenarios}}
  #   Project ID: EL

  Background:
    Given an existing Jira Story with key "{{jira_id_for_update_scenarios}}" that has attachments
    And I am an authenticated Jira user

  Scenario: Successfully retrieve attachment content
    When I request all attachments content for the issue
    Then the response should include at least one attachment
    And each attachment should have filename, size, and content URL
    And the content should be downloadable

  # EXPECTED OUTPUT (preserved):
  # Confirmation message stating the attachment content was retrieved successfully.