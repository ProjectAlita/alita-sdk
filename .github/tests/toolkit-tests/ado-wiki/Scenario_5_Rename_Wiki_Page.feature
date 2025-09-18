@ado @wiki @page @rename @functional
Feature: Rename Wiki Page in Azure DevOps
  The system must allow renaming of wiki pages so that page organization and navigation can be improved.

  # Original Input Context (preserved)
  # Tool: Rename wiki page
  # Test type: functional
  # Test Data:
  #   Wiki Name: "{{wiki_identified}}"
  #   Original Page Path: "{{original_page_path}}"
  #   New Page Path: "{{new_page_path}}"

  Background:
    Given I am an authenticated ADO user with permission to rename wiki pages
    And a wiki exists with name "{{wiki_identified}}"
    And a wiki page exists at path "{{original_page_path}}"
    And the target path "{{new_page_path}}" is available

  Scenario: Successfully rename a wiki page
    When I rename the wiki page from "{{original_page_path}}" to "{{new_page_path}}" in wiki "{{wiki_identified}}"
    Then the page should be renamed successfully
    And the response should confirm the new page path
    And the page should no longer exist at the original path "{{original_page_path}}"
    And the page should be accessible at the new path "{{new_page_path}}"
    And the page content should remain unchanged
    And any existing links should be updated or redirected

  # EXPECTED OUTPUT (preserved):
  # Confirmation that the wiki page was renamed successfully with the new path and preserved content.