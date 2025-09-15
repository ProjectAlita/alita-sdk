@jira @story @comments @images @functional
Feature: Retrieve comments with image descriptions of a User Story
  The system must return enriched comment data including image alt/descriptions for accessibility.

  # Original Input Context (preserved)
  # Test name: Tool - Get comments with image descriptions
  # Test type: functional
  # Test Data:
  #   Jira ID: {{jira_id_for_update_scenarios}}
  #   Project ID: EL

  Background:
    Given an existing Jira Story with key "{{jira_id_for_update_scenarios}}" that has comments with images
    And I am an authenticated Jira user

  Scenario: Successfully retrieve comments including image descriptions
    When I request comments with image description enrichment
    Then the response should include a comments collection
    And comments containing images should include image description metadata
    And no image reference should lack a description field

  # EXPECTED OUTPUT (preserved):
  # Confirmation message stating the comments with image descriptions were retrieved successfully.