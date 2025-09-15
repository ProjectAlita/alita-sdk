@testrail @cases @get @filter @functional
Feature: Retrieve test cases by filter from TestRail
  The system must allow users to retrieve filtered test cases based on specific criteria.

  # Original Input Context (preserved)
  # Test name: Tool - Get Cases by Filter
  # Test type: functional
  # Test Data:
  #   Project ID: "{{project_id}}"

  Background:
    Given I am an authenticated TestRail user with permission to view test cases
    And the TestRail project exists with ID "{{project_id}}"

  Scenario: Successfully retrieve test cases by filter
    When I request test cases with the following JSON filter argument:
      """
      {
        "project_id": "{{project_id}}",
        "priority_id": 4
        " updated_by": 2
      }
      """
    Then I should receive a filtered list of test cases
    And all returned test cases should match the specified criteria
    And the response should include test case details
    And the response should include the total count of filtered cases

  # EXPECTED OUTPUT (preserved):
  # A confirmation message stating the filtered test cases were retrieved successfully, including the filtered results.