@jira @story @create @functional
Feature: Create a new User Story in Jira
  The system must allow creation of a new User Story issue so that project work can be tracked.

  # Original Input Context (preserved)
  # Test name: Tool - Create Issue
  # Test type: functional
  # Test Data:
  #   Issue type: Story
  #   Project ID: EL
  #   Summary: [Test] - User Story
  #   Description:
  #     As a Data Analyst, I want to fetch JIRA issue data into the EDA dashboard so I can analyze project trends.
  #       ### Acceptance Criteria
  #         - Able to connect to JIRA API using token.
  #         - Issue data (summary, status, type, created/resolved dates) is fetched into a DataFrame.
  #         - Data is refreshable.

  Background:
    Given I am an authenticated Jira user with permission to create issues
    And the Jira project key is "EL"

  Scenario: Successfully create a new User Story
    When I create a Story issue with summary "[Test] - User Story" and description:
      """
      As a Data Analyst, I want to fetch JIRA issue data into the EDA dashboard so I can analyze project trends.
      ### Acceptance Criteria
      - Able to connect to JIRA API using token.
      - Issue data (summary, status, type, created/resolved dates) is fetched into a DataFrame.
      - Data is refreshable.
      """
    Then the issue should be created successfully
    And the response should contain a new Jira issue key
    And I can retrieve the newly created issue by its key
    And the issue type should be "Story"
    And the issue summary should be "[Test] - User Story"
    And the issue description should contain "Able to connect to JIRA API using token."

  # EXPECTED OUTPUT (preserved):
  # A confirmation message stating the user story was created successfully, including a new Jira Link for User Story.
  # The agent should verify this by successfully retrieving the user story's details using the new Jira ID.