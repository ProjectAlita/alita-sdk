@artifacts @files @create @functional
Feature: Create a new file in Artifacts storage
  The system must allow creation of files so that documents and data can be stored in the system.

  # Original Input Context (preserved)
  # Tool: Create File
  # Test type: functional
  # Test Data:
  #   Bucket Name: "{{bucket_name}}"
  #   Filename: "{{filename}}" - Complete filename with extension (e.g., "document.txt", "data.csv", "report.xlsx")
  #   Content: Stringified content based on file format

  Background:
    Given I am an authenticated user with Artifacts write access
    And the bucket "{{bucket_name}}" exists

  Scenario: Successfully create a text file
    When I create a file with filename "{{filename}}" in bucket "{{bucket_name}}" and "filedata":
      """
      {
        "Sheet1": [
          ["Name", "Age", "City"],
          ["Alice", 25, "New York"],
          ["Bob", 30, "San Francisco"],
          ["Charlie", 35, "Los Angeles"]
        ]
      }
      """
    Then the response should return the file creation successfully
    And the file should exist in bucket "{{bucket_name}}"
    And the filename should equal "{{filename}}"
    And the file should include content field
    And the file should include size field

  Scenario: Successfully create an Excel data file (.xlsx)
    When I create a file with filename "{{filename}}" in bucket "{{bucket_name}}" and "filedata":
      """
      {
        "Sheet1": [
          ["Name", "Age", "City"],
          ["Alice", 25, "New York"],
          ["Bob", 30, "San Francisco"],
          ["Charlie", 35, "Los Angeles"]
        ]
      }
      """
    Then the response should return the file creation successfully
    And the Excel file should exist in bucket "{{bucket_name}}"
    And the filename should equal "{{filename}}"
    And the file should include structured data format
    And the file should include Sheet1 content

  # EXPECTED OUTPUT (preserved):
  # Successful creation of the specified file with filename and content confirmation.