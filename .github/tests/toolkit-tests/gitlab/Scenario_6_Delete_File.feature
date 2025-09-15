@gitlab @file @delete @functional
Feature: Delete a file from a Gitlab repository
  The system must allow users to delete files for code and documentation maintenance.

  # Original Input Context (preserved)
  # Test name: Tool - Delete File
  # Test type: functional
  # Test Data:
  #   Repository: hrachsg/toolkit-testing
  #   Branch: "{{branch_name}}"
  #   File: "{{file_name}}"

  Background:
    Given the repository "hrachsg/toolkit-testing" contains a file "{{file_name}}"
    And I am an authenticated Gitlab user with write access

  Scenario: Successfully delete a file
    When I delete "{{file_name}}"
    Then the file should no longer exist in the repository
    And the commit history should reflect the deletion

  # EXPECTED OUTPUT (preserved):
  # A confirmation message stating the file was deleted successfully, including commit details.
