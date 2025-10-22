@ado @collections @list @functional
Feature: List collections in Azure DevOps system
  The system must allow listing of available collections for data organization understanding and workflow management.

  # Original Input Context (preserved)
  # Tool: list_collections
  # Test type: functional
  # Test Data:
  #   No mandatory parameters required

  Background:
    Given I am an authenticated Azure DevOps user with system access
    And there are collections available in the system

  @positive @list-collections
  Scenario: User successfully lists available collections
    When I select the "list_collections" tool
    And I click run
    Then I should see a list of all available collections
    And each collection should display name and metadata information
    And the operation should complete successfully

  # EXPECTED OUTPUT (preserved):
  # Complete list of available collections with names, descriptions, and metadata
  # for effective data organization and workflow management within Azure DevOps.
