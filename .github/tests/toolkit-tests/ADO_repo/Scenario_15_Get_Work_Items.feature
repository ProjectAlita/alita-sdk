@ado @work-items @get @functional
Feature: Get work items from Azure DevOps project
  The system must allow retrieval of work items for task prioritization, reporting, and issue summary provision within workflows.

  # Original Input Context (preserved)
  # Tool: get_work_items
  # Test type: functional
  # Test Data:
  #   Project Name: "{{project_name}}"
  #   Work Item Type: "{{work_item_type}}" (optional)

  Background:
    Given I am an authenticated Azure DevOps user with project access
    And work items exist in the project "{{project_name}}"

  @positive @get-work-items
  Scenario: User successfully retrieves work items
    When I select the "get_work_items" tool
    And I specify project name "{{project_name}}"
    And I specify work item type "{{work_item_type}}"
    And I click run
    Then I should see a list of work items from the project
    And each work item should display ID, title, and status information
    And the operation should complete successfully

  # EXPECTED OUTPUT (preserved):
  # Comprehensive list of work items with IDs, titles, types, statuses, and assignees
  # for effective task management, reporting, and workflow prioritization within Azure DevOps projects.
