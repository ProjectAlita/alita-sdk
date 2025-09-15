@gitlab @pr @create @functional
Feature: Create a pull request in Gitlab
  The system must allow users to create pull requests for code review and merging.

  # Original Input Context (preserved)
  # Test name: Tool - Create Pull Request
  # Test type: functional
  # Test Data:
  #   Repository: hrachsg/toolkit-testing
  #   Source Branch: "{{branch_name}}"
  #   Target Branch: master

  Background:
    Given I have a branch "{{branch_name}}" with changes in repository "hrachsg/toolkit-testing"

  Scenario: Successfully create a pull request
    When I create a pull request to merge "{{branch_name}}" into "master"
    Then the pull request should be created and visible in the repository

  # EXPECTED OUTPUT (preserved):
  # A confirmation message stating the pull request was created successfully, including PR details.
