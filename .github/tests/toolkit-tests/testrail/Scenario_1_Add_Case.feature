@testrail @case @add @functional
Feature: Add a new test case in TestRail
  The system must allow users to create new test cases for test management and tracking.

  # Original Input Context (preserved)
  # Test name: Tool - Add Case
  # Test type: functional
  # Test Data:
  #   Project ID: "{{project_id}}"
  #   Section ID: "{{section_id}}"
  #   Title: "Test Case - Add Case Tool Validation"
  #   Description: "This test case validates the functionality of the Add Case tool in TestRail"

  Background:
    Given I am an authenticated TestRail user with permission to add test cases
    And the TestRail project exists with ID "{{project_id}}"
    And the test section exists with ID "{{section_id}}"

  Scenario: Successfully add a new test case
    When I add a test case with title "User Authentication - Login Validation Test" and
    description "This test case validates user login functionality including valid credentials, invalid credentials, and session management. It ensures proper authentication flow and error handling mechanisms are working correctly." 
    to section "{{section_id}}" with the following
    
     case properties:
      {
         "template_id": 2,
         "type_id": 2,
         "priority_id": 4,
         "estimate": "30m",
         "refs": "REQ-AUTH-001, DEF-LOGIN-002",
         "custom_test_case_version": "",
         "custom_preconds": "User must be authenticated and have permission to add test cases to the TestRail project",
         "custom_steps_separated": [
             {
                 "content": "Navigate to TestRail project and select the target test suite",
                 "expected": "Test suite is accessible and displays the correct section structure"
             },
             {
                 "content": "Click on 'Add Test Case' button and fill in the required fields with valid data",
                 "expected": "Test case form is displayed with all mandatory fields available for input"
             },
             {
                 "content": "Set test case properties including template, type, priority, and estimate",
                 "expected": "All properties are correctly applied and visible in the test case preview"
             },
             {
                 "content": "Save the test case and verify it appears in the test suite",
                 "expected": "Test case is successfully created with a unique ID and appears in the designated section"
             },
             {
                 "shared_step_id": 1
             }
         ]
      }

    Then the test case should be created successfully
    And the response should contain a new test case ID
    And I can retrieve the newly created test case by its ID
    And the test case title should be "User Authentication - Login Validation Test"
    And the test case description should be "This test case validates user login functionality including valid credentials, invalid credentials, and session management. It ensures proper authentication flow and error handling mechanisms are working correctly."

  # EXPECTED OUTPUT (preserved):
  # A confirmation message stating the test case was created successfully, including the new test case ID.