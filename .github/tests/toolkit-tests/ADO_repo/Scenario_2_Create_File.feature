@ado @file @create @functional
Feature: Create new file in Azure DevOps repository
  The system must allow creation of new files for automated code generation, documentation, and configuration management.

  # Original Input Context (preserved)
  # Tool: create_file
  # Test type: functional
  # Test Data:
  #   Repository Name: "27e65563-62b8-4834-9259-88bb56f47146"
  #   File Path: "{{file_path}}"
  #   File Content: "{{file_content}}"
  #   Branch Name: "{{base_branch}}"

  Background:
    Given I am an authenticated Azure DevOps user with repository write access
    And the branch "{{base_branch}}" exists in the repository

  @positive @create-file
  Scenario: User successfully creates a new file
    When I select the "create_file" tool
    And I specify repository "27e65563-62b8-4834-9259-88bb56f47146"
    And I specify file path "{{file_path}}"
    And I enter file content "{{file_content}}"
    And I specify branch name "{{base_branch}}"
    And I click run
    Then a new file should be created successfully
    And the file should contain the specified content
    And the operation should complete successfully

  # EXPECTED OUTPUT (preserved):
  # Confirmation of successful file creation with file path, branch context, and commit details
  # for automated code file, documentation, and configuration file generation workflows.
