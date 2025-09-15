@testrail @cases @add @bulk @functional
Feature: Add multiple test cases in TestRail
  The system must allow users to create multiple test cases in bulk for efficient test management.

  # Original Input Context (preserved)
  # Test name: Tool - Add Cases
  # Test type: functional
  # Test Data:
  #   Project ID: "{{project_id}}"
  #   Section ID: "{{section_id}}"
  #   Number of Cases: 2
  #   Case 1: "Password Reset - Email Validation Test"
  #   Case 2: "User Profile - Data Update Validation Test"

  Background:
    Given I am an authenticated TestRail user with permission to add test cases
    And the TestRail project exists with ID "{{project_id}}"
    And the test section exists with ID "{{section_id}}"

  Scenario: Successfully add multiple test cases in bulk
    When I add 2 test cases to section "{{section_id}}" with the following case data:
    
    Case 1:
    {
       "title": "Password Reset - Email Validation Test",
       "template_id": 2,
       "type_id": 1,
       "priority_id": 3,
       "estimate": "20m",
       "refs": "REQ-PWD-001, DEF-LOGIN-002",
       "custom_test_case_version": "",
       "custom_preconds": "User account exists in the system and email service is configured",
       "custom_steps_separated": [
           {
               "content": "Navigate to the login page and click 'Forgot Password' link",
               "expected": "Password reset form is displayed with email input field"
           },
           {
               "content": "Enter a valid registered email address and submit the request",
               "expected": "System displays confirmation message that reset email has been sent"
           },
           {
               "content": "Check email inbox for password reset message within 5 minutes",
               "expected": "Password reset email is received with valid reset link"
           },
           {
               "content": "Click the reset link and verify it opens the password reset page",
               "expected": "Password reset page loads with secure token validation"
           },
           {
               "shared_step_id": 1
           }
       ]
    }
    
    Case 2:
    {
       "title": "User Profile - Data Update Validation Test",
       "template_id": 2,
       "type_id": 2,
       "priority_id": 2,
       "estimate": "25m",
       "refs": "REQ-PROFILE-002, DEF-UPDATE-004",
       "custom_test_case_version": "",
       "custom_preconds": "User is logged in with valid session and has profile editing permissions",
       "custom_steps_separated": [
           {
               "content": "Access user profile settings from the main navigation menu",
               "expected": "Profile page loads with current user information displayed correctly"
           },
           {
               "content": "Modify personal information fields including name, phone, and address",
               "expected": "Form fields accept valid input and show real-time validation feedback"
           },
           {
               "content": "Click Save Changes button and confirm the update operation",
               "expected": "System displays success message and updates are reflected immediately"
           },
           {
               "content": "Refresh the page and verify all changes have been persisted",
               "expected": "Updated information remains saved and displays correctly after page reload"
           }
       ]
    }

    Then both test cases should be created successfully
    And the response should contain new test case IDs for each case
    And I can retrieve both newly created test cases by their IDs
    And the first test case title should be "Password Reset - Email Validation Test"
    And the second test case title should be "User Profile - Data Update Validation Test"
    And both test cases should have their respective descriptions and custom steps properly configured

  # EXPECTED OUTPUT (preserved):
  # A confirmation message stating both test cases were created successfully, including the new test case IDs for each case.