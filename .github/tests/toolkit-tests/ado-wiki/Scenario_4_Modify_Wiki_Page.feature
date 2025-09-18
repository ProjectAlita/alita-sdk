@ado @wiki @page @modify @functional
Feature: Modify Wiki Page in Azure DevOps
  The system must allow modification of wiki page content so that documentation can be updated and maintained.

  # Original Input Context (preserved)
  # Tool: Modify wiki page
  # Test type: functional
  # Test Data:
  #   Wiki Name: "{{wiki_identified}}"
  #   Page Path: "{{page_path}}"
  #   Updated Content: Enhanced documentation with examples

  Background:
    Given I am an authenticated ADO user with permission to edit wiki pages
    And a wiki exists with name "{{wiki_identified}}"
    And a wiki page exists at path "{{page_path}}"

  Scenario: Successfully modify a wiki page content
    When I modify the wiki page at path "{{page_path}}" in wiki "{{wiki_identified}}" with updated content:
      """
      # Updated Documentation
      
      This page has been updated with enhanced content for testing purposes.
      
      ## New Section
      - Added comprehensive examples
      - Improved formatting and structure
      - Updated with current best practices
      
      Last updated: $(date)
      """
    Then the page should be updated successfully
    And the response should contain the updated page version
    And retrieving the page should show the new content
    And the page content should contain "enhanced content for testing purposes"
    And the page version should be incremented

  # EXPECTED OUTPUT (preserved):
  # Confirmation that the wiki page was modified successfully with new version number and updated content.