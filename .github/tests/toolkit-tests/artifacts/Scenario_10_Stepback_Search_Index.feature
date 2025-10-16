@artifacts @index @stepback-search @advanced @functional
Feature: Perform stepback search on indexed data
  The system must allow advanced stepback search to find documents through indirect relationships and expanded context using broader context.

  # Original Input Context (preserved)
  # Tool: Stepback Search Index
  # Test type: functional
  # Test Data:
  #   Query: {{Query}} - The search query text (required)
  #   Collection_suffix: "Collection_suffix" (e.g. docs)- Specific dataset to search (optional, max 7 characters)

  Background:
    Given I am an authenticated user with Artifacts access
    And there are indexed documents available for stepback searching

  @positive @stepback-search-index
  Scenario: User successfully performs stepback search on indexed data
    When I select the "Stepback Search Index" tool
    And I enter "{{Query}}" in the Query field
    And I enter "Collection_suffix" in the Collection suffix field "docs"
    And I click run
    Then I should see comprehensive search results with broader context
    And the system should display both direct and indirect matches
    And the operation should complete successfully

  # EXPECTED OUTPUT (preserved):
  # Enhanced search results showing both direct and indirect matches with stepback reasoning.
  # The agent should display how the search was expanded and why certain documents were included.