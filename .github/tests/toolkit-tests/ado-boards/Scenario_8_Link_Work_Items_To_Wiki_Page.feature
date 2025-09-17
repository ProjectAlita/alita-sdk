@ado @workitem @wiki @link @functional
Feature: Link Work Items to a Wiki Page in Azure DevOps
  The system must allow linking work items to wiki pages to provide contextual documentation references.

  # Original Input Context (preserved)
  # Tool: Link work items to wiki page
  # Test type: functional
  # Test Data:
  #   Work Item IDs: "{{work_item_id}}"
  #   Wiki Page Path: "{{wiki_page_path}}"

  Background:
    Given I am an authenticated ADO user with permission to link work items to wiki pages
    And the following work items exist: "{{work_item_id}}"
    And the wiki page path "{{wiki_page_path}}" exists

  Scenario: Successfully link work items to a wiki page
    When I link the work items "{{work_item_ids}}" to wiki page "{{wiki_page_path}}"
    Then the link operation should succeed
    And each work item should reference the wiki page link

  # EXPECTED OUTPUT (preserved):
  # Wiki links added to each work item.