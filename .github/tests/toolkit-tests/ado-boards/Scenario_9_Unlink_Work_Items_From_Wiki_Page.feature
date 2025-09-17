@ado @workitem @wiki @unlink @functional
Feature: Unlink Work Items from a Wiki Page in Azure DevOps
  The system must allow removing wiki page links from work items to keep relationships current.

  # Original Input Context (preserved)
  # Tool: Unlink work items from wiki page
  # Test type: functional
  # Test Data:
  #   Work Item IDs: "{{work_item_id}}"
  #   Wiki Page Path: "{{wiki_page_path}}"

  Background:
    Given I am an authenticated ADO user with permission to unlink work items from wiki pages
    And the following work items exist: "{{work_item_id}}"
    And the wiki page path "{{wiki_page_path}}" exists and is currently linked to those work items

  Scenario: Successfully unlink work items from a wiki page
    When I unlink the work items "{{work_item_id}}" from wiki page "{{wiki_page_path}}"
    Then the unlink operation should succeed
    And each work item should no longer reference the wiki page link

  # EXPECTED OUTPUT (preserved):
  # Wiki links removed from each work item.