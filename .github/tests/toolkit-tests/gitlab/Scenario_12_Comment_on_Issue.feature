@gitlab @issue @comment @functional
Feature: Add a comment to a Gitlab issue
  The system must allow users to add comments to issues for collaboration and tracking.

  # Original Input Context (preserved)
  # Test name: Tool - Comment on Issue
  # Test type: functional
  # Test Data:
  #   Repository: hrachsg/toolkit-testing
  #   Issue ID: "{{issue_id}}"
  #   Comment: "{{content}}"

  Background:
    Given an issue exists with ID "{{issue_id}}" in repository "hrachsg/toolkit-testing"
    And I am an authenticated Gitlab user with permission to comment

  Scenario: Successfully add a comment to an issue
    When I add the comment "{{content}}" to the issue
    Then the comment should be visible in the issue discussion

  # EXPECTED OUTPUT (preserved):
  # A confirmation message stating the comment was added successfully, including comment details.
