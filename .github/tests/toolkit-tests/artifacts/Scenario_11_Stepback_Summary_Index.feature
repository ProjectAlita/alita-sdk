@artifacts @index @summary @stepback @advanced @functional
Feature: Generate stepback summary from indexed data
  The system must create comprehensive summaries using stepback analysis to provide enhanced context and insights.

  # Original Input Context (preserved)
  # Tool: Stepback Summary Index
  # Test type: functional
  # Test Data:
  #   Query: {{Query}} - What topic or information to search for and summarize (required)
  #   Collection_suffix: docs - Specific dataset to search within (optional, max 7 characters)

  Background:
    Given I am an authenticated user with Artifacts access
    And there are indexed documents available for stepback summary generation

  @positive @stepback-summary-index
  Scenario: User successfully generates stepback summary from indexed data
    When I select the "Stepback Summary Index" tool
    And I enter "{{Query}}" in the Query field
    And I enter "docs" in the Collection suffix field
    And I click run
    Then I should see a comprehensive summary with stepback analysis
    And the system should provide enhanced context and insights
    And the operation should complete successfully

  # EXPECTED OUTPUT (preserved):
  # A comprehensive summary document with stepback analysis showing both direct and contextual information.
  # The agent should present the summary in a structured format with clear sections and source references.