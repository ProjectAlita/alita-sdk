@ado @wiki @page @get @functional
Feature: Get Wiki Page by Path in Azure DevOps
  The system must allow retrieval of wiki pages by path so that page content can be accessed using hierarchical navigation.

  # Original Input Context (preserved)
  # Tool: Get wiki page by path
  # Test type: functional
  # Test Data:
  #   Wiki Name: "{{wiki_identified}}"
  #   Page Path: "{{page_path}}"

  Background:
    Given I am an authenticated ADO user with permission to view wiki pages
    And a wiki exists with name "{{wiki_identified}}"
    And a wiki page exists at path "{{page_path}}"

  Scenario: Successfully retrieve a wiki page by path
    When I get the wiki page at path "{{page_path}}" from wiki "{{wiki_identified}}"
    Then the response should return the page content successfully
    And the page path should equal "{{page_path}}"
    And the page should include a title
    And the page should include content or markdown text
    And the page should include version and last modified information

  # EXPECTED OUTPUT (preserved):
  # Wiki page object containing path, title, content, and metadata accessed by hierarchical path.