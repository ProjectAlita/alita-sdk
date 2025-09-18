@ado @wiki @page @get @functional
Feature: Get Wiki Page by ID in Azure DevOps
  The system must allow retrieval of wiki pages by ID so that page content can be accessed.

  # Original Input Context (preserved)
  # Tool: Get wiki page by id
  # Test type: functional
  # Test Data:
  #   Wiki Name: "{{wiki_identified}}"
  #   Page ID: "{{page_id}}"

  Background:
    Given I am an authenticated ADO user with permission to view wiki pages
    And a wiki exists with name "{{wiki_identified}}"
    And a wiki page exists with ID "{{page_id}}"

  Scenario: Successfully retrieve a wiki page by ID
    When I get the wiki page with ID "{{page_id}}" from wiki "{{wiki_identified}}"
    Then the response should return the page content successfully
    And the page ID should equal "{{page_id}}"
    And the page should include a title
    And the page should include content or markdown text
    And the page should include version information

  # EXPECTED OUTPUT (preserved):
  # Wiki page object containing ID, title, content, and version metadata.