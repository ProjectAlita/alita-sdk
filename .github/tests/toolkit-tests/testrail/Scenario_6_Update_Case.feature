@testrail @case @update @functional
Feature: Update an existing test case in TestRail
  The system must allow users to update test case details for maintenance and improvement.

  # Original Input Context (preserved)
  # Test name: Tool - Update Case
  # Test type: functional
  # Test Data:
  #   Test Case ID: "{{case_id}}"
  #   Updated Title: "API Integration - Database Transaction Test"
  #   Updated Priority: High (3)
  #   Updated Description: Comprehensive API testing with database validation

  Background:
    Given I am an authenticated TestRail user with permission to update test cases
    And a test case exists with ID "{{case_id}}"

  Scenario: Successfully update a test case with enhanced details
    When I update test case "{{case_id}}" with the following enhanced properties:
    
    {
       "title": "API Integration - Database Transaction Test",
       "template_id": 2,
       "type_id": 2,
       "priority_id": 3,
       "estimate": "45m",
       "refs": "STORY-INT-012",
       "custom_test_case_version": "2.1",
       "custom_preconds": "API service is running, database is accessible, test data is prepared, and authentication tokens are valid",
       "custom_steps_separated": [
           {
               "content": "Establish API connection and authenticate with valid credentials",
               "expected": "API responds with 200 status and valid authentication token is received"
           },
           {
               "content": "Execute POST request to create new database record with test payload",
               "expected": "API returns 201 status with newly created record ID and confirmation message"
           },
           {
               "content": "Verify database transaction by querying the created record directly",
               "expected": "Database contains the new record with correct data and proper timestamps"
           },
           {
               "content": "Perform UPDATE operation via API to modify specific record fields",
               "expected": "API responds with 200 status and updated record reflects the changes accurately"
           },
           {
               "content": "Execute rollback scenario and verify data integrity mechanisms",
               "expected": "System handles rollback correctly without data corruption or orphaned records"
           }
       ]
    }

    Then the test case should be updated successfully
    And the response should contain the updated test case details
    And I can retrieve the updated test case by its ID "{{case_id}}"
    And the test case title should be "API Integration - Database Transaction Test"
    And the test case priority should be "3" (High)
    And the test case estimate should be "45m"
    And the custom steps should contain 5 detailed validation steps
    And the test case version should be updated to "2.1"

  # EXPECTED OUTPUT (preserved):
  # A confirmation message stating the test case was updated successfully, including the updated test case details with enhanced API integration testing specifications.