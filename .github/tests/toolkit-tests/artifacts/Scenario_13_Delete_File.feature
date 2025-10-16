@artifacts @files @delete @functional
Feature: Delete files from Artifacts storage
  The system must allow users to delete files so they can manage storage space and remove unwanted content.

  # Original Input Context (preserved)
  # Tool: DeleteFile
  # Test type: functional
  # Test Data:
  #   Filename: {{filename}} - Name of the file to delete (required)

  Background:
    Given I am an authenticated user with Artifacts delete access
    And there are files available for deletion

  @positive @delete-file
  Scenario: User successfully deletes a file
    When I select the "DeleteFile" tool
    And I enter "{{filename}}" in the Filename field
    And I click run
    Then I should see confirmation of file deletion
    And the system should remove the specified file
    And the operation should complete successfully
    Given I have read-only access to the bucket
    When I attempt to delete file "{{filename}}" from bucket "{{bucket_name}}"
    Then the deletion should be rejected
    And the response should indicate insufficient permissions
    And the file should remain unchanged

  # EXPECTED OUTPUT (preserved):
  # A confirmation message stating the file was deleted successfully with operation details.
  # The agent should verify deletion by attempting to list files and confirming the file is no longer present.