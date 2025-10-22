@ado @file @delete @functional
Feature: Delete file from Azure DevOps repository
  The system must allow deletion of files for cleanup tasks, removing obsolete files, and automated file management.

  # Original Input Context (preserved)
  # Tool: delete_file
  # Test type: functional
  # Test Data:
  #   Repository Name: "{{repository_name}}"
  #   File Path: "{{file_path}}"
  #   Branch Name: "{{base_branch}}"

  Background:
    Given I am an authenticated Azure DevOps user with repository write access
    And the file "{{file_path}}" exists in branch "{{base_branch}}"

  @positive @delete-file
  Scenario: User successfully deletes a file
    When I select the "delete_file" tool
    And I specify repository "{{repository_name}}"
    And I specify file path "{{file_path}}"
    And I specify branch name "{{base_branch}}"
    And I click run
    Then the file should be deleted successfully
    And the file should no longer exist in the repository
    And the operation should complete successfully

  # EXPECTED OUTPUT (preserved):
  # Confirmation of successful file deletion with file path, branch context, and commit details
  # for automated cleanup, obsolete file removal, and temporary file management workflows.
