@gitlab @file @update @functional
Feature: Update an existing file in a Gitlab repository
  The system must allow users to update files for documentation and code maintenance.

  # Original Input Context (preserved)
  # Test name: Tool - Update File
  # Test type: functional
  # Test Data:
  #   Repository: hrachsg/toolkit-testing
  #   File: "{{file_name}}"
  #   Content: "{{content}}"
  #   Branch: "{{branch_name}}"

  Background:
    Given the repository "hrachsg/toolkit-testing" contains "{{file_name}}" on branch "{{branch_name}}"
    And I am an authenticated Gitlab user with write access

  Scenario: Successfully update "{{file_name}}"
    When I update "{{file_name}}" with content "{{content}}" on branch "{{branch_name}}"
    Then the file should reflect the updated content
    And the commit history should show the update

  # EXPECTED OUTPUT (preserved):
  # A confirmation message stating the file was updated successfully, including commit details.
