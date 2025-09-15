@gitlab @file
 @append @functional
Feature: Append content to an existing file in a Gitlab repository
  The system must allow users to append content to files for documentation and code updates.

  # Original Input Context (preserved)
  # Test name: Tool - Append File
  # Test type: functional
  # Test Data:
  #   Repository: hrachsg/toolkit-testing
  #   File: "{{file_name}}"
  #   Content: "{{file_content}}"
  #   Branch: "{{branch_name}}"

  Background:
    Given I am an authenticated Gitlab user with write access to the repository "hrachsg/toolkit-testing"
    And the repository contains a file named "{{file_name}}" on branch "{{branch_name}}"

  Scenario: Successfully append content to "{{file_name}}"
    When I append the text "{{file_content}}" to "{{file_name}}" on branch "{{branch_name}}"
    Then the file should contain the new appended content
    And the commit history should reflect the change

  # EXPECTED OUTPUT (preserved):
  # A confirmation message stating the file was updated successfully, including commit details.
