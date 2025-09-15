@jira @story @fields @images @functional
Feature: Retrieve a field with image descriptions of a User Story
  The system must enrich field content (e.g., description) with image alt text / descriptions for accessibility tooling.

  # Original Input Context (preserved)
  # Test name: Tool - Get field with image descriptions
  # Test type: functional
  # Test Data:
  #   Jira ID: {{jira_id_for_update_scenarios}}
  #   Project ID: EL

  Background:
    Given an existing Jira Story with key "{{jira_id_for_update_scenarios}}" whose description contains inline images
    And I am an authenticated Jira user

  Scenario: Successfully retrieve a field with image descriptions
    When I request the description field with image description enrichment
    Then the response should include the description field
    And embedded images should include description metadata
    And no embedded image should have empty alt/description data

  # EXPECTED OUTPUT (preserved):
  # Confirmation message stating the field with image descriptions was retrieved successfully.