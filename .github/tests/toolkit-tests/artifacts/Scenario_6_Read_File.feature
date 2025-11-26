@artifacts @files @read @functional
Feature: Read file content from Artifacts storage
  The system must allow reading of file content so that users can access and review stored documents.

  # Original Input Context (preserved)
  # Tool: ReadFile
  # Test type: functional
  # Test Data:
  #   Bucket_name: {{bucket_name}} - Bucket to navigate to
  #   Filename: {{filename}} - Filename to search and read content from

  Background:
    Given I am an authenticated user with Artifacts read access
    And the bucket "{{bucket_name}}" exists

  @positive @read-file
  Scenario: User attempts to read file content from bucket
    When I select the "ReadFile" tool
    And I navigate to bucket "{{bucket_name}}"
    And I search for file "{{filename}}" in the bucket
    And I click run
    Then if the file "{{filename}}" exists in the bucket
      Then I should see the file content displayed
      And the system should show the complete file content
      And the operation should complete successfully
    But if the file "{{filename}}" doesn't exist in the bucket
      Then I should see a message that the test couldn't be executed
      And the system should display "File doesn't exist in the bucket"

  # EXPECTED OUTPUT (preserved):
  # The complete file content retrieved and displayed with filename confirmation.