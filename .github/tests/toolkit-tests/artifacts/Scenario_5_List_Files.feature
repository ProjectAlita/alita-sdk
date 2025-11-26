@artifacts @files @list @functional
Feature: List files in Artifacts storage bucket
  The system must allow listing of files in a bucket so that users can browse and manage their stored content.

  # Original Input Context (preserved)
  # Tool: ListFiles
  # Test type: functional
  # Test Data:
  #   Bucket Name: "{{bucket_name}}" - Bucket to list files from

  Background:
    Given I am an authenticated user with Artifacts access
    And the bucket "{{bucket_name}}" exists with stored files

  Scenario: Successfully list all files in the bucket
    When I list files in bucket "{{bucket_name}}"
    Then the response should return the file listing successfully
    And the response should contain a list of files in the bucket
    And I can view all files stored in the bucket "{{bucket_name}}"
    And each file should include filename and metadata
    And the bucket name should be "{{bucket_name}}"
    And the files should be displayed from the toolkit bucket

  # EXPECTED OUTPUT (preserved):
  # A list of all files in the specified bucket with filenames and metadata displayed from the toolkit.