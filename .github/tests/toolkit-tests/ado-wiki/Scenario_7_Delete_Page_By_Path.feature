@ado @wiki @page @delete @functional
Feature: Delete Wiki Page by Path in Azure DevOps
  The system must allow deletion of wiki pages by path so that pages can be removed using hierarchical navigation.

  # Original Input Context (preserved)
  # Tool: Delete page by path
  # Test type: functional
  # Test Data:
  #   Wiki Name: "{{wiki_identified}}"
  #   Page Path: "{{new_page_path}}"

  Background:
    Given I am an authenticated ADO user with permission to delete wiki pages
    And a wiki exists with name "{{wiki_identified}}"
    And a wiki page exists at path "{{new_page_path}}"

  Scenario: Successfully delete a wiki page by path
    When I delete the wiki page at path "{{new_page_path}}" from wiki "{{wiki_identified}}"
    Then the page should be deleted successfully
    And the response should confirm the deletion operation
    And the page at path "{{new_page_path}}" should no longer exist
    And attempting to retrieve the page should return a not found error
    And the wiki navigation structure should be updated accordingly

  # EXPECTED OUTPUT (preserved):
  # Confirmation that the wiki page was deleted successfully and is no longer accessible via its path.