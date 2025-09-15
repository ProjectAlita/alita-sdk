@gitlab @commits @get @functional
Feature: Retrieve commit history from a Gitlab repository
  The system must allow users to view commit history for auditing and collaboration.

  # Original Input Context (preserved)
  # Test name: Tool - Get Commits
  # Test type: functional
  # Test Data:
  #   Repository: hrachsg/toolkit-testing
  #   Branch: "{{branch_name}}"

  Background:
    Given I am an authenticated Gitlab user with access to the repository "hrachsg/toolkit-testing"

  Scenario: Successfully retrieve commit history
    When I request the commit history for branch "{{branch_name}}"
    Then I should receive a list of commits with messages and timestamps

  # EXPECTED OUTPUT (preserved):
  # A confirmation message stating the commit history was retrieved successfully, including commit details.
