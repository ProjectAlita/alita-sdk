@artifacts @index @create @functional
Feature: Index data in Artifacts system
  The system must allow indexing of data so that it can be stored and made searchable for future retrieval.

  # Original Input Context (preserved)
  # Tool: Index data
  # Test type: functional
  # Test Data:
  #   Collection Suffix: "docs" - Collection suffix to index data into

  Background:
    Given I am an authenticated user with Artifacts access
    And the collection with suffix "docs" is available

  Scenario: Successfully index data into collection
    When I index data with collection suffix "docs"
    Then the response should return the indexing operation successfully
    And the data should be indexed into the collection
    And I can verify the data was indexed properly
    And the collection suffix should be "docs"
    And the indexed data should be searchable
    And the data should be stored in the docs collection

  # EXPECTED OUTPUT (preserved):
  # A confirmation message stating the data was indexed successfully into the docs collection.