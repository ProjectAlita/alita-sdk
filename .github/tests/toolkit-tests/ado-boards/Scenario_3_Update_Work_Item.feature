@ado @workitem @update @functional
Feature: Update an existing Work Item in Azure DevOps
  The system must allow updating a work item so that its state and metadata remain current.

  # Original Input Context (preserved)
  # Tool: Update work item
  # Test type: functional
  # Test Data:
  #   Work Item ID: "{{work_item_id}}"
  #   Update: Change title and description

  Background:
    Given I am an authenticated ADO user with permission to edit work items
    And a work item exists with ID "{{work_item_id}}"

  Scenario: Successfully update a work item title and description
    When I update the work item with ID "{{work_item_id}}" setting:
      | field       | value                                             |
      | System.Title | [Updated] - User Story Creation via Toolkit       |
      | System.Description | Updated description content for validation |
    Then the work item should be updated successfully
    And retrieving the work item should show the updated title
    And the work item description should contain "Updated description content"

  # EXPECTED OUTPUT (preserved):
  # Confirmation that the work item update succeeded and new values are persisted.