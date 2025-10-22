@ado @file @read @functional
Feature: Read file content from Azure DevOps repository
  The system must allow reading of file content to retrieve code snippets, configuration files, and documentation for context provision.

  # Original Input Context (preserved)
  # Tool: read_file
  # Test type: functional
  # Test Data:
  #   Repository Name: "{{repository_name}}"
  #   File Path: "{{file_path}}"
  #   Branch Name: "{{base_branch}}"

  Background:
    Given I am an authenticated Azure DevOps user with repository read access
    And the file "{{file_path}}" exists in branch "{{base_branch}}"

  @positive @read-file
  Scenario: User successfully reads file content
    When I select the "read_file" tool
    And I specify repository "{{repository_name}}"
    And I specify file path "{{file_path}}"
    And I specify branch name "{{base_branch}}"
    And I click run
    Then I should see the complete file content
    And the content should be properly formatted and readable
    And the operation should complete successfully

  # EXPECTED OUTPUT (preserved):
  # Complete file content retrieved from the specified branch with proper formatting,
  # enabling contextual code analysis and documentation access within workflows.
