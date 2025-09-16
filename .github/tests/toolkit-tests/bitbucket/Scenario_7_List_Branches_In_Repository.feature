@bitbucket @branch @list @functional
Feature: List all branches in Bitbucket repository
  The system must allow users to retrieve all branches so that repository structure can be understood.

  # Original Input Context (preserved)
  # Test name: Tool - List Branches in Repository
  # Test type: functional


  Background:
    Given I am an authenticated Bitbucket user with repository access
    And multiple branches exist in the repository

  Scenario: Successfully list all repository branches
    When I list all branches in the repository
    Then the response should contain a list of all branches
    And each branch should have last activity timestamp

  # EXPECTED OUTPUT (preserved):
  # A list of all branches with their names, latest commit hashes, and last activity information.
  # The agent should display branch details in a readable format.