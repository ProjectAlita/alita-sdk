@gitlab @files @list @functional
Feature: List all files in a Gitlab repository
  The system must allow users to view all files for project management and code discovery.

  # Original Input Context (preserved)
  # Test name: Tool - List Files
  # Test type: functional
  # Test Data:
  #   Repository: hrachsg/toolkit-testing
  #   Branch: "{{branch_name}}"

  Background:
    Given the repository "hrachsg/toolkit-testing" contains multiple files on branch "{{branch_name}}"

  Scenario: Successfully list all files
    When I request the list of files from branch "{{branch_name}}"
    Then I should receive the names and paths of all files

  # EXPECTED OUTPUT (preserved):
  # A confirmation message stating the file list was retrieved successfully, including file details.
