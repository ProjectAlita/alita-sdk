@ado @file @update @functional
Feature: Update file content in Azure DevOps repository
  The system must allow updating of existing files for automated code modifications, documentation updates, and configuration changes.

  # Original Input Context (preserved)
  # Tool: update_file
  # Test type: functional
  # Test Data:
  #   Repository Name: "{{repository_name}}"
  #   File Path: "{{file_path}}"
  #   New Content: "{{new_content}}"
  #   Branch Name: "{{base_branch}}"

  Background:
    Given I am an authenticated Azure DevOps user with repository write access
    And the file "{{file_path}}" exists in branch "{{base_branch}}"

  @positive @update-file
  Scenario: User successfully updates file content
    When I select the "update_file" tool
    And I specify repository "{{repository_name}}"
    And I specify file path "{{file_path}}"
    And I enter new content "{{new_content}}"
    And I specify branch name "{{base_branch}}"
    And I click run
    Then the file should be updated successfully
    And the file should contain the new content
    And the operation should complete successfully

  # EXPECTED OUTPUT (preserved):
  # Confirmation of successful file update with file path, branch context, and commit information
  # for automated code updates, documentation synchronization, and configuration management workflows.
