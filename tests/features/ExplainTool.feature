Feature: Explain Tool Functionality

  Background:
    Given I open '$url' url

  @toolkit
  Scenario: User clicks the 'EXPLAIN TOOL' button to view tool description
    # Assume a tool is already selected in the Test Settings panel
    When I click 'EXPLAIN TOOL'
    Then I expect 'Tool:' to be visible
    And I expect 'Parameters:' to be visible