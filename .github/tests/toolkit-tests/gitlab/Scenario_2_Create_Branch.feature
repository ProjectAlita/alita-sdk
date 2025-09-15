@gitlab @branch @create @functional
Feature: Create a new branch in a Gitlab repository
  The system must allow users to create branches for feature development and collaboration.

  # Original Input Context (preserved)
  # Test name: Tool - Create Branch
  # Test type: functional
  # Test Data:
  #   Repository: hrachsg/toolkit-testing
  #   Branch: "{{branch_name}}"
  #   Source: master

  Background:
    Given I am an authenticated Gitlab user with access to the repository "hrachsg/toolkit-testing"

  Scenario: Successfully create a new branch
    When I create a branch named "{{branch_name}}" from "master"
    Then the new branch "{{branch_name}}" should exist in the repository

  # EXPECTED OUTPUT (preserved):
  # A confirmation message stating the branch was created successfully, including branch details.
