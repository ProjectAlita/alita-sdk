@ado @index @data @functional
Feature: Index data in Azure DevOps repository
  The system must allow indexing of repository data for enhanced search and analysis capabilities within workflow processes.

  # Original Input Context (preserved)
  # Tool: index_data
  # Test type: functional
  # Test Data:
  #   Repository Name: "{{repository_name}}"
  #   Data Source: "{{data_source}}"
  #   Collection Suffix: "{{collection_suffix}}"

  Background:
    Given I am an authenticated Azure DevOps user with repository access
    And there is data available for indexing in the repository

  @positive @index-data
  Scenario: User successfully indexes repository data
    When I select the "index_data" tool
    And I specify repository "{{repository_name}}"
    And I specify data source "{{data_source}}"
    And I specify collection suffix "{{collection_suffix}}"
    And I click run
    Then the data should be indexed successfully
    And the indexed data should be available for search operations
    And the operation should complete successfully

  # EXPECTED OUTPUT (preserved):
  # Confirmation of successful data indexing with collection details and indexed content summary
  # for enhanced search and analysis capabilities within Azure DevOps workflows.
