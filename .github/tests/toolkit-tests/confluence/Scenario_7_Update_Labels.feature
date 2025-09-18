@confluence @page @labels @update @functional
Feature: Update labels on a Confluence page
  The system must allow adding and removing labels {{label}} on a Confluence page to support categorization.

  # Original Input Context (preserved)
  # Test name: Tool - Update Labels
  # Test type: functional
  # Test Data:
  #   Page id: "66119"
  #   Labels to add:  "analytics", "docs"
  #   
  #       ### Acceptance Criteria
  #         - Able to connect to Confluence API using token.
  #         - labels are updated correctly.
  #         - label list is retrievable and reflects changes.

  Background:
    Given I am an authenticated Confluence user with permission to edit pages
    And the Confluence space key is "SD"

  Scenario: Successfully update labels for a Confluence page
    When I update labels on page id "66119" to add ["analytics","docs"] and remove ["draft"]
    Then the label update should be successful
    And retrieving labels for page id "66119" should include "analytics" and "docs"
    And should not include "draft"

  # EXPECTED OUTPUT (preserved):
  # A confirmation that labels were updated and verification by retrieving the label list.
