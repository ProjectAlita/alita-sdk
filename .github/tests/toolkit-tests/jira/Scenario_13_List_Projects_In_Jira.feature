@jira @projects @list @functional
Feature: List all projects in Jira
  The system must allow retrieval of available projects for selection and reporting.

  # Original Input Context (preserved)
  # Test name: Tool - List projects
  # Test type: functional
  # Test Data:
  #   List all projects

  Background:
    Given I am an authenticated Jira user

  Scenario: Successfully list all projects
    When I request the list of projects
    Then the response should include at least one project
    And each project should have a key and name
    And the project list should include the project key "EL"

  # EXPECTED OUTPUT (preserved):
  # Confirmation message stating the projects were retrieved successfully and verified by project names.