@artifacts @files @overwrite @functional
Feature: Overwrite an existing file in Artifacts storage
  The system must allow overwriting file content so that documents can be completely replaced with new versions.

  # Original Input Context (preserved)
  # Tool: OverwriteData
  # Test type: functional
  # Test Data:
  #   Filename: "{{filename}}" - Filename to overwrite
  #   Filedata: Stringified content to overwrite existing file content

  Background:
    Given I am an authenticated user with Artifacts write access
    And the file "{{filename}}" exists with existing content

  Scenario: Successfully overwrite an existing file
    When I overwrite filename "{{filename}}" with "filedata" "This is completely new content that will replace all existing file data. The previous content will be entirely overwritten with this new text content."
    Then the file should be overwritten successfully
    And the response should contain the updated file information
    And I can retrieve the file and verify the new content
    And the filename should be "{{filename}}"
    And the file should contain only the new overwritten content
    And the original content should no longer exist

  # EXPECTED OUTPUT (preserved):
  # A confirmation message stating the file was overwritten successfully with filename and new content details.