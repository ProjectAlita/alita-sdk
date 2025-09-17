@ado @workitem @link @functional
Feature: Link two Work Items in Azure DevOps
  The system must allow linking related work items so relationships can be tracked.

  # Original Input Context (preserved)
  # Tool: Link work items
  # Test type: functional
  # Test Data:
  #   Source Work Item ID: "{{work_item_id}}"
  #   Target Work Item ID: 25
  #   Relation Type: related

  Background:
    Given I am an authenticated ADO user with permission to modify work item links
    And a work item exists with ID "{{work_item_id}}"
    And a work item exists with ID 25

  Scenario: Successfully link two work items
    When I link work item "{{work_item_id}}" to work item 25 with relation type "related"
    Then the linking operation should succeed
    And retrieving the source work item should show a relation to the target
    And the relation type should be "related"

  # EXPECTED OUTPUT (preserved):
  # Source work item now includes relation entry referencing target ID.