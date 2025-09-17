@ado @workitem @search @functional
Feature: Search for Work Items in Azure DevOps
  The system must allow searching for work items so users can locate relevant tasks by criteria.

  # Original Input Context (preserved)
  # Tool: Search work items
  # Test type: functional
  # Test Data:
  #   WIQL Query: Work items in Doing state with Priority = 1 for project

  Background:
    Given I am an authenticated ADO user with permission to search work items

  Scenario: Successfully search work items by WIQL
    When I search for work items in project "{{project_name}}" using WIQL:
      """
      SELECT [System.Id], [System.Title], [System.State], [Priority]
      FROM WorkItems
        AND [System.State] = 'Doing'
        AND [Priority] = 1
      ORDER BY [System.ChangedDate] DESC
      """
    Then the response should return a list of work items
    And each result should include an id and title
    And at least one work item should be in state "Doing"
    And all returned work items should have priority 1

  # EXPECTED OUTPUT (preserved):
  # List of work items in Doing state with priority 1 matching the WIQL criteria.