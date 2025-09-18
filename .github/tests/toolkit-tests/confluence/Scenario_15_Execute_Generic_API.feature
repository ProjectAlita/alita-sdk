@confluence @api @generic @functional
Feature: Execute a generic Confluence API call
  The system must allow executing arbitrary Confluence REST API calls for flexibility.

  # Original Input Context (preserved)
  # Test name: Tool - Execute Generic API
  # Test type: functional
  # Test Data:
  #   Method: " (GET, POST, PUT, DELETE)"
  #   Endpoint: /rest/api/SD
  #       ### Acceptance Criteria
  #         - Able to connect to Confluence API using token.
  #         - Generic API calls return expected HTTP responses.

  Background:
    Given I am an authenticated Confluence user with permission to call APIs
    And the Confluence base URL is configured

  Scenario: Successfully execute a generic API GET call
    When I execute a GET request to "/rest/api/SD"
    Then the response should return a list of spaces or a valid HTTP response
    And the response status should be in 200   201   204
  # EXPECTED OUTPUT (preserved):
  # A successful HTTP response containing API-specific data; verification by checking status and expected fields.
