@gitlab @issues @list @functional
Feature: List all issues in a Gitlab repository
  The system must allow users to view all issues for project management and tracking.

  # Original Input Context (preserved)
  # Test name: Tool - Get Issues
  # Test type: functional
  # Test Data:
  #   Repository: hrachsg/toolkit-testing

  Background:
    Given I am an authenticated Gitlab user with access to the repository "hrachsg/toolkit-testing"

  Scenario: Successfully list all issues
    When I request the list of issues
    Then I should receive all open and closed issues with their details

  # EXPECTED OUTPUT (preserved):
  # A confirmation message stating the issue list was retrieved successfully, including issue details.
