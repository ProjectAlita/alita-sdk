@ado @wiki @get @functional
Feature: Get Wiki information in Azure DevOps
  The system must allow retrieval of wiki metadata so that wiki properties can be accessed.

  # Original Input Context (preserved)
  # Tool: Get wiki
  # Test type: functional
  # Test Data:
  #   Wiki Name: "{{wiki_identified}}"

  Background:
    Given I am an authenticated ADO user with permission to access wikis
    And a wiki exists with name "{{wiki_identified}}"

  Scenario: Successfully retrieve wiki information
    When I get the wiki "{{wiki_identified}}"
    Then the response should return the wiki details successfully
    And the wiki name should equal "{{wiki_identified}}"
    And the wiki should include a repository reference
    And the wiki should include creation and modification metadata

  # EXPECTED OUTPUT (preserved):
  # Wiki object containing name, ID, repository information, and metadata.