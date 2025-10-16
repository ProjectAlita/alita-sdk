@artifacts @files @append @functional
Feature: Append data to an existing file in Artifacts storage
  The system must allow appending content to existing files so that data can be incrementally updated without rewriting.

  # Original Input Context (preserved)
  # Tool: AppendData
  # Test type: functional
  # Test Data:
  #   Filename: "{{filename}}" - Filename to append data to
  #   Filedata: Stringified content to append

  Background:
    Given I am an authenticated user with Artifacts write access
    And the file "{{filename}}" exists with initial content

  Scenario: Successfully append data to an existing file
    When I append data to filename "{{filename}}" with filedata "This is additional random text content appended to the file. {"status": "success", "timestamp": "2025-10-15T10:00:00Z", "operation": "append_data"}"
    Then the file should be updated successfully
    And the response should contain the updated file information
    And I can retrieve the file and verify the appended content
    And the filename should be "{{filename}}"
    And the file should contain the original content
    And the file should contain the newly appended data

  # EXPECTED OUTPUT (preserved):
  # A confirmation message stating the data was appended successfully, including file size and modification details.