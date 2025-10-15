@artifacts @bucket @create @functional
Feature: Create new bucket in Artifacts storage
  The system must allow users to create new storage buckets so they can organize files and collections effectively.

  # Original Input Context (preserved)
  # Test name: Tool - Create New Bucket
  # Test type: functional
  # Test Data:
  #   Bucket Name: Agent should generate unique bucket name (no underscores allowed)
  #   Expiration Measure: Unit of time for bucket expiration (days, weeks, months, years)
  #   Expiration Value: Number of units for expiration time
  #   ***IMPORTANT*** Underscore `_` is prohibited in bucket name and should be replaced by `-`

  Background:
    Given I am an authenticated user with Artifacts bucket creation access
    And I have permissions to create new buckets

  Scenario: Successfully create a new bucket with default settings
    Given the agent generates a unique bucket name without underscores (using hyphens instead)
    When I create a new bucket with the following parameters:
      """
      {
        "bucket_name": "{{bucket_name}}",
        "expiration_measure": "weeks",
        "expiration_value": 1
      }
      """
    Then the bucket should be created successfully with default expiration settings
    And the response should confirm the bucket creation
    And the bucket should appear in the list of available buckets
    And the bucket should be accessible for file operations
    And the bucket name should contain only allowed characters (no underscores)
    And the bucket should have expiration set to 1 week

  Scenario: Create bucket with custom expiration settings
    Given the agent generates a unique bucket name without underscores (using hyphens instead)
    When I create a new bucket with custom expiration parameters:
      """
      {
        "bucket_name": "{{bucket_name}}",
        "expiration_measure": "months", 
        "expiration_value": 6
      }
      """
    Then the bucket should be created successfully with custom expiration settings
    And the bucket should have expiration set to 6 months
    And the bucket name should not contain underscores
    And the bucket should be accessible for file operations

  Scenario: Create bucket with different expiration measures
    Given the agent generates a unique bucket name without underscores
    When I create buckets with different expiration measures:
      """
      [
        {
          "bucket_name": "{{bucket_name}}-days",
          "expiration_measure": "days",
          "expiration_value": 30
        },
        {
          "bucket_name": "{{bucket_name}}-years", 
          "expiration_measure": "years",
          "expiration_value": 2
        }
      ]
      """
    Then all buckets should be created with their respective expiration settings
    And the buckets should have different expiration configurations
    And all bucket names should use hyphens instead of underscores

  Scenario: Attempt to create bucket with invalid name (containing underscores)
    When I attempt to create a bucket with name containing underscores "test_bucket_name"
    Then the system should reject the bucket creation
    And the response should indicate that underscores are not allowed in bucket names
    And the system should suggest using hyphens instead
    And no bucket should be created

  Scenario: Create bucket with minimum valid parameters
    Given the agent generates a unique bucket name without underscores
    When I create a new bucket with only the required bucket name parameter:
      """
      {
        "bucket_name": "{{bucket_name}}"
      }
      """
    Then the bucket should be created successfully with default values
    And the expiration measure should default to "weeks"
    And the expiration value should default to 1
    And the bucket should be functional for file operations

  Scenario: Attempt to create bucket with duplicate name
    Given a bucket with name "existing-test-bucket" already exists
    When I attempt to create a new bucket with name "existing-test-bucket"
    Then the creation should fail gracefully
    And the response should indicate the bucket name already exists
    And the original bucket should remain unchanged

  # EXPECTED OUTPUT (preserved):
  # A confirmation message stating the bucket was created successfully with the unique name, expiration settings, and configuration details.
  # The agent should verify creation by listing buckets and confirming the new bucket appears in the list.
  # The agent must ensure bucket names do not contain underscores and use hyphens instead.
  # Default values: expiration_measure = "weeks", expiration_value = 1