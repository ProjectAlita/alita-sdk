@artifacts @files @read @functional
Feature: Read file content from Artifacts storage
  The system must allow reading of file content so that users can access and review stored documents.

  # Original Input Context (preserved)
  # Tool: ReadFile
  # Test type: functional
  # Test Data:
  #   Filename: "{{filename}}" - Filename to read content from

  Background:
    Given I am an authenticated user with Artifacts read access
    And the file "{{filename}}" exists

  Scenario: Successfully read file content
    When I read the content of filename "{{filename}}"
    Then the response should return the file content successfully
    And the response should contain the complete file content
    And I can retrieve and view the file content
    And the filename should be "{{filename}}"
    And the file content should be properly formatted and readable
    And the content should be displayed from the file

  # EXPECTED OUTPUT (preserved):
  # The complete file content retrieved and displayed with filename confirmation.