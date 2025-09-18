@ado @wiki @page @delete @functional
Feature: Delete Wiki Page by ID in Azure DevOps
  The system must allow deletion of wiki pages by ID so that outdated or unwanted content can be removed.

  # Original Input Context (preserved)
  # Tool: Delete page by id
  # Test type: functional
  # Test Data:
  #   Wiki Name: "{{wiki_identified}}"
  #   Page ID: "{{page_id}}"

  Background:
    Given I am an authenticated ADO user with permission to delete wiki pages
    And a wiki exists with name "{{wiki_identified}}"
    And a wiki page exists with ID "{{page_id}}"

  Scenario: Successfully delete a wiki page by ID
    When I delete the wiki page with ID "{{page_id}}" from wiki "{{wiki_identified}}"
    Then the page should be deleted successfully
    And the response should confirm the deletion operation
    And the page with ID "{{page_id}}" should no longer exist
    And attempting to retrieve the page should return a not found error
    And any child pages should be handled according to deletion policy

  # EXPECTED OUTPUT (preserved):
  # Confirmation that the wiki page was deleted successfully and is no longer accessible.