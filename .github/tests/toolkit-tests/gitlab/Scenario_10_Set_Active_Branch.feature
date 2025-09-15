@gitlab @branch @set-active @functional
Feature: Set the active branch in a Gitlab repository
  The system must allow users to set the active branch for context in subsequent operations.

  # Original Input Context (preserved)
  # Test name: Tool - Set Active Branch
  # Test type: functional
  # Test Data:
  #   Repository: hrachsg/toolkit-testing
  #   Branch: "{{branch_name}}"

  Background:
    Given the repository "hrachsg/toolkit-testing" contains multiple branches

  Scenario: Successfully set the active branch
    When I set "{{branch_name}}" as the active branch
    Then subsequent operations should use "{{branch_name}}" as the context

  # EXPECTED OUTPUT (preserved):
  # A confirmation message stating the active branch was set successfully, including branch details.
