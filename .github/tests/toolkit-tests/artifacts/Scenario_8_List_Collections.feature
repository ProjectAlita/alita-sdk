@artifacts @collections @list @functional
Feature: List available collections in Artifacts system
  The system must allow listing of available collections so that users can view and understand the data organization structure.

  # Original Input Context (preserved)
  # Tool: List collections
  # Test type: functional
  # Test Data:
  #   No mandatory parameters required

  Background:
    Given I am an authenticated user with Artifacts access
    And there are collections available in the system

  @positive @list-collections
  Scenario: User successfully lists available collections
    When I select the "List collections" tool
    And I click run
    Then I should see a list of all available collections
    And the system should display collection names and metadata
    And the operation should complete successfully

  # EXPECTED OUTPUT (preserved):
  # A formatted list of collections with names, descriptions, document counts, and access levels.
  # The agent should display this information in a readable table or structured format.