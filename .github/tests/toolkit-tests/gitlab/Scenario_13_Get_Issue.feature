@gitlab @issue @get @functional
Feature: Retrieve details of a specific Gitlab issue
  The system must allow users to view issue details for tracking and resolution.

  # Original Input Context (preserved)
  # Test name: Tool - Get Issue
  # Test type: functional
  # Test Data:
  #   Repository: hrachsg/toolkit-testing
  #   Issue ID: "{{issue_id}}"

  Background:
    Given an issue exists with ID "{{issue_id}}" in repository "hrachsg/toolkit-testing"
    And I am an authenticated Gitlab user

  Scenario: Successfully retrieve issue details
    When I request the details of issue "{{issue_id}}"
    Then I should receive the issue's title, description, and status

  # EXPECTED OUTPUT (preserved):
  # A confirmation message stating the issue details were retrieved successfully, including issue data.
