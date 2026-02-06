# Confluence Toolkit Test Suite

Test suite for Confluence toolkit under `alita_sdk/tools/confluence/`.

## Test Coverage

| Tool | Test Files | Priority | Status |
|------|------------|----------|--------|
| get_page_tree | test_case_01 | Critical | ✅ Created |
| get_pages_with_label | test_case_02 | Critical | ✅ Created |
| read_page_by_id | test_case_03 | Critical | ✅ Created |
| search_pages | test_case_04, test_case_11 | Critical, High | ✅ Created |
| search_by_title | test_case_05 | Critical | ✅ Created |
| get_page_id_by_title | test_case_06 | Critical | ✅ Created |
| create_page, delete_page | test_case_07 | Critical | ✅ Created |
| list_pages_with_label | test_case_08 | Critical | ✅ Created |
| get_page_attachments | test_case_09 | Critical | ✅ Created |
| update_page_by_id | test_case_10 | Critical | ✅ Created |
| site_search | test_case_11, test_case_12 | Critical, High | ✅ Created |
| get_page_with_image_descriptions | test_case_13, test_case_14 | Critical, High | ✅ Created |
| execute_generic_confluence | test_case_15, test_case_16 | Critical, High | ✅ Created |
| create_pages | test_case_17, test_case_18 | Critical, High | ✅ Created |
| update_page_by_title | test_case_19, test_case_20 | Critical, High | ✅ Created |
| update_pages | test_case_21, test_case_22 | Critical, High | ✅ Created |
| update_labels | test_case_23, test_case_24 | Critical, High | ✅ Created |
| add_file_to_page | test_case_25, test_case_26 | Critical, High | ✅ Created |

**Total**: 18 tools covered, 26 test files

## Setup Artifacts

- Confluence Toolkit: ${CONFLUENCE_TOOLKIT_ID}
- Confluence Toolkit Name: ${CONFLUENCE_TOOLKIT_NAME}
- Artifact Toolkit: ${ARTIFACT_TOOLKIT_ID} (bucket: confluence-test-bucket)
- Test File Artifact: ${TEST_ARTIFACT_ID} (test_upload.txt)
- Test Pages (existing in Confluence space AT):
  - Page ID: 104038676 (Template - Project plan)
  - Page ID: 138969168 (TC-003 Page with label)
  - Page ID: 139395168 (Page with images)
  - Page ID: 140869772 (Page with attachments)

## Environment Variables

Required variables (set in .env):
- CONFLUENCE_API_KEY: Confluence API token
- CONFLUENCE_BASE_URL: Confluence instance URL (default: https://epamelitea.atlassian.net/)
- CONFLUENCE_USERNAME: Confluence username/email
- CONFLUENCE_SPACE: Confluence space key (default: AT)
- CONFLUENCE_SECRET_NAME: Secret name for credentials (default: confluence)
- CONFLUENCE_TOOLKIT_NAME: Toolkit name on platform (default: confluence-testing)

Optional variables:
- CONFLUENCE_CONFIG_PATH: Path to base toolkit config (default: ../../configs/confluence-config.json)

## Test Creation History

### Run: 2026-02-02

- Request: Create tests for confluence toolkit
- Tools discovered: 18 tools (via get_available_tools())
- Test files created: 16 new files (test_case_11 through test_case_26)
- Test files skipped (duplicates): 0
- Config created/updated: pipeline.yaml execution order updated

### New Tests Created (test_case_11 - test_case_26):

**site_search (CF11-CF12)**
- CF11: Happy path - searches with results
- CF12: Edge case - no results found

**get_page_with_image_descriptions (CF13-CF14)**
- CF13: Happy path - page with images
- CF14: Edge case - page not found

**execute_generic_confluence (CF15-CF16)**
- CF15: Happy path - GET request
- CF16: Edge case - POST request with params

**create_pages (CF17-CF18)**
- CF17: Happy path - batch creation multiple pages
- CF18: Edge case - single page in batch

**update_page_by_title (CF19-CF20)**
- CF19: Happy path - content update by title
- CF20: Edge case - page title not found

**update_pages (CF21-CF22)**
- CF21: Happy path - batch update different content
- CF22: Edge case - batch update same content

**update_labels (CF23-CF24)**
- CF23: Happy path - add labels to pages
- CF24: Edge case - no page IDs provided

**add_file_to_page (CF25-CF26)**
- CF25: Happy path - append file to page (uses artifact from setup)
- CF26: Edge case - prepend file to page (uses artifact from setup)

## Pipeline Setup

The test suite performs the following setup steps:

1. **Confluence Configuration**: Creates secret with API credentials
2. **Confluence Toolkit**: Creates/updates toolkit with space AT configuration
3. **Artifact Toolkit**: Creates toolkit for file storage (bucket: confluence-test-bucket)
4. **Test File Creation**: Creates test_upload.txt artifact for file attachment tests

This ensures CF25 and CF26 tests have a pre-existing file artifact to attach to Confluence pages.

## Notes

- All test validations are derived from actual tool implementation (return statements)
- Tests use existing Confluence pages in space AT for read operations
- Write operations (create/update/delete) use timestamp-based unique identifiers
- Test isolation: Each test uses only setup artifacts, no cross-test dependencies
