@ado @workitem @get @functional
Feature: Retrieve an existing Work Item in Azure DevOps
  The system must allow retrieval of a specific work item so that its details can be viewed.

  # Original Input Context (preserved)
  # Tool: Get work item
  # Test type: functional
  # Test Data:
  #   Work Item ID: "{{work_item_id}}"

  Background:
    Given I am an authenticated ADO user with permission to view work items
    And a work item exists with ID "{{work_item_id}}"

  Scenario: Successfully retrieve a work item by ID
    When I get the work item with ID "{{work_item_id}}"
    Then the response should return the work item successfully
    And the work item ID should equal "{{work_item_id}}"
    And the work item should include a title field
    And the work item should include a URL field

  # EXPECTED OUTPUT (preserved):
  # Successful retrieval of the specified work item with its core fields.