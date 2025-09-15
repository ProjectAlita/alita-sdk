@gitlab @folders @list @functional
Feature: List all folders in a Gitlab repository
  The system must allow users to view all folders for project organization and code discovery.

  # Original Input Context (preserved)
  # Test name: Tool - List Folders
  # Test type: functional
  # Test Data:
  #   Repository: hrachsg/toolkit-testing
  #   Branch: "{{branch_name}}"

  Background:
    Given the repository "hrachsg/toolkit-testing" contains multiple folders on branch "{{branch_name}}"

  Scenario: Successfully list all folders
    When I request the list of folders from branch "{{branch_name}}"
    Then I should receive the names and paths of all folders

  # EXPECTED OUTPUT (preserved):
  # A confirmation message stating the folder list was retrieved successfully, including folder details.
