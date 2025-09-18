@confluence @page @attachments @read @functional
Feature: Get attachments for a Confluence page
  The system must list and optionally download attachments associated with a Confluence page.

  # Original Input Context (preserved)
  # Test name: Tool - Get Page Attachments
  # Test type: functional
  # Test Data:
  #   Page id: "43679747"
  #       ### Acceptance Criteria
  #         - Able to connect to Confluence API using token.
  #         - Attachment list is returned with metadata and download links where applicable.

  Background:
    Given I am an authenticated Confluence user with permission to view pages and attachments
    And the Confluence space key is "SD"

  Scenario: Successfully retrieve attachments for a page and validate download link
    # Tool: Execute generic confluence
    # Purpose: List attachments for a specific Confluence page and verify an attachment can be fetched
    Given the following tool input:
      | field        | value                                           |
      | Method       | GET                                             |
      | Relative Url | /rest/api/content/43679747?expand=version,body.storage\  |
      | Params       | {"limit":25,"start":0}                       |

    When I execute the "Execute generic confluence" tool with the above input
    Then the response status should be 200
    And the response body should contain an array of attachments
    And each attachment item should include the fields: id, contentType, title, _links.download
    And at least one attachment should have a non-empty _links.download value

    # Optional: verify we can retrieve the first attachment's download URL
    When I save the first attachment's download URL as "attachmentDownloadUrl"
    And I request the URL stored in "attachmentDownloadUrl" using Method "GET"
    Then the download response status should be 200
    And the download response body should be non-empty

  # EXPECTED OUTPUT (preserved):
  # A list of attachments with metadata and download URLs; verification by attempting to fetch an attachment.
