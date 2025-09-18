@confluence @page @search @title @functional
Feature: Search Confluence pages by title
  The system must allow searching pages specifically by title to quickly locate named documents.

  # Original Input Context (preserved)
  # Test name: Tool - Search by Title
  # Test type: functional
  # Test Data:
  #   Title: "[Test] - Confluence Page"
  #       ### Acceptance Criteria
  #         - Able to connect to Confluence API using token.
  #         - Pages with matching titles "Ping" are returned.

  Background:
    Given I am an authenticated Confluence user with permission to view pages
    And the Confluence space key is "SD"

  Scenario: Successfully search pages by title "Ping" 
    When I search pages with title "Ping" 
    Then the response should contain one or more pages whose title matches the query
    And each returned page's title should contain the search string

  # EXPECTED OUTPUT (preserved):
  # A list of pages matching the exact or partial title query that can be opened.
