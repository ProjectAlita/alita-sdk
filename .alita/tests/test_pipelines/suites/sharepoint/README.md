# SharePoint Toolkit Test Suite

Test suite for SharePoint toolkit under `alita_sdk/tools/sharepoint/`.

## Test Coverage

| Tool | Test Files | Priority | Status |
|------|------------|----------|--------|
| get_lists | test_case_01, test_case_02 | Critical, High | ✅ Complete |
| read_list | test_case_03, test_case_04 | Critical, High | ✅ Complete (Self-contained) |
| get_list_columns | test_case_05, test_case_06 | Critical, High | ✅ Complete |
| create_list_item | test_case_07, test_case_08 | Critical, High | ✅ Complete |
| get_files_list | test_case_09, test_case_10 | Critical, High | ✅ Complete |
| read_document | test_case_11, test_case_12 | Critical, High | ✅ Complete (Self-contained) |
| upload_file | test_case_13, test_case_14 | Critical, High | ✅ Complete (Self-contained) |
| add_attachment_to_list_item | test_case_15, test_case_16 | Critical, High | ✅ Complete (Self-contained) |

**Coverage**: 8/8 tools (100%), 16/16 test files complete

## Setup Artifacts

The setup stage in `pipeline.yaml` creates the following artifacts:

- **SharePoint Configuration**: OAuth credentials (client_id, client_secret, site_url)
- **Toolkit Instance**: ${SHAREPOINT_TOOLKIT_ID} - Created toolkit for test execution
- **Test List**: ${TEST_LIST_NAME} (default: `DO_NOT_DELETE_AlitaTestList`) - SharePoint list for list operations
- **Test Folder**: ${TEST_FOLDER} (default: `Shared Documents/DO_NOT_DELETE_AlitaTestFiles`) - Folder for file operations
- **Test File**: ${TEST_FILE_NAME} (default: `DO_NOT_DELETE_test-document.txt`) - Sample file for read tests

## Environment Variables

Required variables (set in `.alita/tests/test_pipelines/.env`):

### SharePoint Credentials (Required)
- `SHAREPOINT_SITE_URL`: SharePoint site URL (e.g., https://contoso.sharepoint.com/sites/MySite)
- `SHAREPOINT_CLIENT_ID`: OAuth client ID for SharePoint authentication
- `SHAREPOINT_CLIENT_SECRET`: OAuth client secret for SharePoint authentication

### Configuration Files
- `SHAREPOINT_CONFIG_PATH`: Path to SharePoint configuration JSON (default: ../../configs/sharepoint-config.json)

### Secret Names
- `SHAREPOINT_SECRET_NAME`: Name for SharePoint configuration secret (default: sharepoint)

### Toolkit Configuration
- `SHAREPOINT_TOOLKIT_NAME`: Name for toolkit instance (default: sharepoint-testing)

### Test Artifacts (Optional - have defaults)
- `TEST_LIST_NAME`: SharePoint list name for tests (default: DO_NOT_DELETE_AlitaTestList)
- `TEST_FOLDER`: Folder path for file tests (default: Shared Documents/DO_NOT_DELETE_AlitaTestFiles)
- `TEST_FILE_NAME`: Test file name (default: DO_NOT_DELETE_test-document.txt)

## Test Scenarios

### List Operations (SP01-SP08)
- **SP01**: Get all lists - Verify list enumeration
- **SP02**: Get lists metadata validation - Verify metadata completeness
- **SP03**: Read list items - Self-contained: creates item, then reads list
- **SP04**: Read non-existent list - Error handling
- **SP05**: Get list columns - Retrieve column metadata
- **SP06**: Get columns invalid list - Error handling
- **SP07**: Create list item - Basic item creation
- **SP08**: Create item missing fields - Validation error handling

### File Operations (SP09-SP14)
- **SP09**: List root files - Basic file listing
- **SP10**: List files in folder - Folder filtering
- **SP11**: Read document content - Self-contained: uploads file, then reads it
- **SP12**: Read non-existent file - Error handling
- **SP13**: Upload new file - Self-contained: creates inline file content
- **SP14**: Upload replace existing - Self-contained: uploads twice to test replacement

### Attachment Operations (SP15-SP16)
- **SP15**: Add attachment to item - Self-contained: creates item, adds attachment
- **SP16**: Add attachment replace - Self-contained: creates item, adds twice to test replacement

## Prerequisites

Before running tests, ensure:

1. **SharePoint Site Access**: Valid SharePoint site with appropriate permissions
2. **OAuth App Registration**: Client ID and secret with required permissions
3. **Test List**: Create `DO_NOT_DELETE_AlitaTestList` SharePoint list manually (required for list operations)
4. **Environment Configuration**: All required variables set in `.env` file

**Note**: Tests are self-contained where possible. File and attachment tests create their own test data inline using the `filedata` parameter. Only the test list (for list operations) needs to exist before running tests.

## Running Tests

```bash
# Run all SharePoint tests
cd .alita/tests/test_pipelines
./run_test.sh --local suites/sharepoint

# Run specific test
./run_test.sh --local suites/sharepoint SP01

# Run with verbose output
./run_test.sh --local suites/sharepoint --verbose
```

## Test Isolation

Tests are designed for independence and minimal setup:

### Self-Contained Tests
- **File Upload Tests (SP13-SP14)**: Create file content inline using `filedata` parameter
- **Attachment Tests (SP15-SP16)**: Create list items and attachments inline within each test
- **Read Document Test (SP11)**: Uploads file first, then reads it
- **Read List Test (SP03)**: Creates list item first, then reads list

### Shared Setup Tests
- **List Operations (SP01-SP02, SP04-SP08)**: Use existing test list from setup
- **File List Operations (SP09-SP10)**: Use existing folder structure

### Key Benefits
- ✅ Most tests can run without manual data preparation
- ✅ Each test creates and manages its own test data
- ✅ Tests can run in any order
- ✅ Minimal cleanup required (toolkit and pipelines removed in cleanup stage)
- ✅ Timestamp-based naming prevents conflicts between test runs

## Notes

- Tests use SharePoint REST API with Graph API fallback
- Authentication supports both OAuth (client credentials) and access token
- File operations support both artifact storage and direct content
- Large files (>4MB) use chunked upload automatically
- System/hidden lists and fields are excluded from results

## Test Creation History

### Run: 2026-02-19 (Initial Creation)

- **Request**: Create test cases for SharePoint toolkit
- **Tools discovered**: 8 SharePoint tools
- **Test files created**: 12/16 (Critical + High for 6 tools)
- **Test files skipped**: 0 (new suite)
- **Config created**: Yes (pipeline.yaml, README.md)
- **Artifacts defined**: Test list, test folder, test file with DO_NOT_DELETE prefix

### Run: 2026-02-19 (Completion + Self-Contained Updates)

- **Request**: Implement missing tests and make tests self-contained
- **Missing tests added**: 4 tests (SP13-SP16 for upload_file and add_attachment_to_list_item)
- **Self-contained updates**: 
  - SP03: Now creates list item before reading
  - SP11: Now uploads file before reading
  - SP13-SP16: Create data inline using filedata parameter
- **Final coverage**: 8/8 tools (100%), 16/16 test files complete
- **Architecture**: All file/attachment tests are fully self-contained; list operations use pre-existing test list
