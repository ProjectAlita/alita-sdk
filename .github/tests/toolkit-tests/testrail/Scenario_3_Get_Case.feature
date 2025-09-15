@testrail @case @get @functional
Feature: Retrieve a specific test case from TestRail
  The system must allow users to retrieve test case details for review and analysis.

  # Original Input Context (preserved)
  # Test name: Tool - Get Case
  # Test type: functional
  # Test Data:
  #   Test Case ID: "{{case_id}}"

  Background:
    Given I am an authenticated TestRail user with permission to view test cases
    And a test case exists with ID "{{case_id}}"

  Scenario: Successfully retrieve a test case
    When I request the test case with ID "{{case_id}}"
    Then I should receive the test case details
    And the response should contain the test case title
    And the response should contain the test case description
    And the response should contain the test case status
    And the response should contain the test case creation date

  # EXPECTED OUTPUT (preserved):
  # A confirmation message stating the test case was retrieved successfully, including all test case details.