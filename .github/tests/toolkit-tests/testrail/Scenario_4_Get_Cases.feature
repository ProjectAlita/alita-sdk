@testrail @cases @get @list @functional
Feature: Retrieve all test cases from TestRail
  The system must allow users to retrieve all test cases for project management and oversight.

  # Original Input Context (preserved)
  # Test name: Tool - Get Cases
  # Test type: functional
  # Test Data:
  #   Project ID: "{{project_id}}"
  #   Suite ID: "{{section_id}}"

  Background:
    Given I am an authenticated TestRail user with permission to view test cases
    And the TestRail project exists with ID "{{project_id}}"
    And the test suite exists with ID "{{section_id}}"

  Scenario: Successfully retrieve all test cases
    When I request all test cases from project "{{project_id}}" and suite "{{section_id}}"
    Then I should receive a list of all test cases
    And each test case should contain basic information
    And the response should include test case IDs
    And the response should include test case titles

  # EXPECTED OUTPUT (preserved):
  # A confirmation message stating the test cases were retrieved successfully, including the count and list of test cases.