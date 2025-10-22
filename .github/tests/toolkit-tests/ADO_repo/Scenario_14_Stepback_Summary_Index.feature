@ado @stepback @summary @index @advanced @functional
Feature: Generate stepback summary from indexed data in Azure DevOps system
  The system must allow generation of comprehensive summaries using stepback analysis for enhanced context and insights.

  # Original Input Context (preserved)
  # Tool: stepback_summary_index
  # Test type: functional
  # Test Data:
  #   Query: "{{query}}" - Topic or information to search for and summarize (required)
  #   Collection Suffix: "{{collection_suffix}}" (optional)

  Background:
    Given I am an authenticated Azure DevOps user with system access
    And there is indexed data available for stepback summary generation

  @positive @stepback-summary-index
  Scenario: User successfully generates stepback summary from indexed data
    When I select the "stepback_summary_index" tool
    And I enter "{{query}}" in the Query field
    And I enter "{{collection_suffix}}" in the Collection suffix field
    And I click run
    Then I should see a comprehensive summary with stepback analysis
    And the summary should provide enhanced context and insights
    And the operation should complete successfully

  # EXPECTED OUTPUT (preserved):
  # Comprehensive summary with stepback analysis providing enhanced context and insights
  # for effective information synthesis and decision-making within Azure DevOps workflows.
