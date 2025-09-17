@ado @workitem @create @functional
Feature: Create a new Work Item in Azure DevOps
  The system must allow creation of a new work item so that project work can be tracked effectively.

  # Original Input Context (preserved)
  # Tool: Create work item
  # Test type: functional
  # Test Data:
  #   Work Item Type: Issue
  #   Title: "[Test] - Issue Creation via Toolkit"
  #   Description: Basic issue for automated validation

  Background:
    Given I am an authenticated ADO user with permission to manage work items

  Scenario: Successfully create a new Issue work item
    # Acceptance Criteria (condensed): correct type & title; description persisted; response has valid ID
    When I create a "Issue" work item with title "[Test] - Issue Creation via Toolkit" and description "As a platform user, I want to create work items through the toolkit so that I can automate planning workflows. Acceptance Criteria: Work item is created with correct type and title; Description is persisted; Response contains valid ID."
    Then the work item should be created successfully
    And the response should contain a new work item ID
    And I can retrieve the newly created work item by its ID
    And the work item type should be "Issue"
    And the work item title should be "[Test] - Issue Creation via Toolkit"
    And the work item description should contain "automate planning workflows"

  # EXPECTED OUTPUT (preserved):
  # A confirmation message stating the work item was created successfully, including its ID and URL.