@bitbucket @file @list @functional
Feature: List files in Bitbucket repository
  The system must allow users to browse repository files so that project structure can be understood.

  # Original Input Context (preserved)
  # Test name: Tool - List Files
  # Test type: functional
  # Test Data:
  #   Branch: "{{branch_name}}"
  #   Path: /tests

  Background:
    Given I am an authenticated Bitbucket user with repository access
    And the branch "{{branch_name}}" contains files

  Scenario: Successfully list files in repository root
    When I list files in the root directory of branch "{{branch_name}}"
    Then the response should contain a list of files and directories
    And the list should include file names and types
    And the list should include directory indicators
    And each file should have size and last modification information

  Scenario: Successfully list files in specific directory
    When I list files in the "/tests" directory of branch "{{branch_name}}"
    Then the response should contain files within the tests directory
    And the list should include subdirectory(if avilable)
    And each item should have appropriate file or directory type

  # EXPECTED OUTPUT (preserved):
  # A structured list of files and directories with their metadata.
  # The agent should display the file tree in an organized, readable format.