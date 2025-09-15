@jira @story @update @functional
Feature: Update an existing User Story description
  Users must be able to update User Story fields including description to refine requirements.

  # Original Input Context (preserved)
  # Test name: Tool - Update issue
  # Test type: functional
  # Test Data:
  #   Jira ID: {{jira_id_for_update_scenarios}}
  #   Project ID: EL
  #   Description: (includes Technical Notes + Acceptance Criteria)

  Background:
    Given an existing Jira Story with key "{{jira_id_for_update_scenarios}}"
    And I am an authenticated Jira user with permission to edit issues

  Scenario: Successfully update the Story description
    When I update the issue description to:
      """
      As a Data Analyst, I want to fetch JIRA issue data into the EDA dashboard so I can analyze project trends.
      ### Acceptance Criteria
      - Able to connect to JIRA API using token.
      - Issue data (summary, status, type, created/resolved dates) is fetched into a DataFrame.
      - Data is refreshable.
      ### Technical Notes
      - Use API v3.
      - Follow best practices for security.
      - Use obfuscated date.
      """
    Then the issue should be updated successfully
    And I can retrieve the updated issue
    And the description should contain "Technical Notes"
    And the description should contain "Use API v3."
    And the description should contain "Use obfuscated date."

  # EXPECTED OUTPUT (preserved):
  # A confirmation message stating the user story was updated successfully, including a Jira Link.
  # Verification by retrieving the issue details using the Jira ID.