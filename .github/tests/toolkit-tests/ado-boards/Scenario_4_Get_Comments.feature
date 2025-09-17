@ado @workitem @comments @get @functional
Feature: Get comments for a Work Item in Azure DevOps
  The system must allow listing of comments on a work item so collaboration context is visible.

  # Original Input Context (preserved)
  # Tool: Get comments
  # Test type: functional
  # Test Data:
  #   Work Item ID: "{{work_item_id}}"

  Background:
    Given I am an authenticated ADO user with permission to view work item comments
    And a work item exists with ID "{{work_item_id}}"

  Scenario: Successfully list comments for a work item
    When I get comments for the work item with ID "{{work_item_id}}"
    Then the response should return a comments collection
    And the result should include a total count field
    And each comment should include an id and created date

  # EXPECTED OUTPUT (preserved):
  # JSON payload containing an array of comment objects with metadata.