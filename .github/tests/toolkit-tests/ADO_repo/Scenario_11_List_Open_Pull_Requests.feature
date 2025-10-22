@ado @pull-requests @list @open @functional
Feature: List open pull requests in Azure DevOps repository
  The system must allow retrieval of open pull requests for workflow monitoring, review management, and development oversight.

  # Original Input Context (preserved)
  # Tool: list_open_pull_requests
  # Test type: functional
  # Test Data:
  #   Repository Name: "{{repository_name}}"

  Background:
    Given I am an authenticated Azure DevOps user with repository access
    And there are open pull requests in the repository

  @positive @list-open-pull-requests
  Scenario: User successfully lists open pull requests
    When I select the "list_open_pull_requests" tool
    And I specify repository "{{repository_name}}"
    And I click run
    Then I should see a list of all open pull requests
    And each pull request should display title, author, and status
    And the operation should complete successfully

  # EXPECTED OUTPUT (preserved):
  # Comprehensive list of open pull requests with titles, authors, creation dates, and current status
  # for effective workflow monitoring and code review management in Azure DevOps.
