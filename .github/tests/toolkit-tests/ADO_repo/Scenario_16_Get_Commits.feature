@ado @commits @get @functional
Feature: Get commits from Azure DevOps repository
  The system must allow retrieval of commit information for code history analysis, change tracking, and development workflow monitoring.

  # Original Input Context (preserved)
  # Tool: get_commits
  # Test type: functional
  # Test Data:
  #   Repository Name: "27e65563-62b8-4834-9259-88bb56f47146"
  #   Branch Name: "{{base_branch}}" (optional)
  #   Commit Count: "{{commit_count}}" (optional)

  Background:
    Given I am an authenticated Azure DevOps user with repository read access
    And commits exist in the repository

  @positive @get-commits
  Scenario: User successfully retrieves commit information
    When I select the "get_commits" tool
    And I specify repository "27e65563-62b8-4834-9259-88bb56f47146"
    And I specify branch name "{{base_branch}}"
    And I specify commit count "{{commit_count}}"
    And I click run
    Then I should see a list of commits from the repository
    And each commit should display hash, message, author, and timestamp
    And the operation should complete successfully

  # EXPECTED OUTPUT (preserved):
  # Comprehensive list of commits with hashes, messages, authors, timestamps, and change summaries
  # for code history analysis, change tracking, and development workflow monitoring in Azure DevOps.
