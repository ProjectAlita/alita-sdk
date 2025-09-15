@gitlab @pr @comment @functional
Feature: Add a comment to a pull request change in Gitlab
  The system must allow users to add comments to pull request changes for review and collaboration.

  # Original Input Context (preserved)
  # Test name: Tool - Create PR Change Comment
  # Test type: functional
  # Test Data:
  #   PR Number: "{{pr_number}}"
  #   Comment: "{{comment_text}}"

  Background:
    Given a pull request exists with number "{{pr_number}}"

  Scenario: Successfully add a comment to a pull request change
    When I add a comment "{{comment_text}}" to pull request "{{pr_number}}"
    Then the comment should appear in the pull request discussion

  # EXPECTED OUTPUT (preserved):
  # A confirmation message stating the comment was added successfully, including comment details.
