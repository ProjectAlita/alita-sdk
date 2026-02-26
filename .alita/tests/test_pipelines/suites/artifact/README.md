# Artifact Toolkit Test Suite

Comprehensive test suite for the artifact toolkit (`alita_sdk/runtime/tools/artifact.py`). This suite validates all file storage and management operations including bucket creation, file operations, searching, and batch processing.

## Test Coverage

| # | Tool | Test File | Priority | Objective |
|---|------|-----------|----------|-----------|
| AT01 | `createNewBucket` | test_case_01_create_new_bucket_happy_path.yaml | Critical | Bucket creation with expiration and sanitization |
| AT02 | `createFile` | test_case_02_create_file_happy_path.yaml | Critical | File creation with content verification |
| AT03 | `createFile` | test_case_03_create_file_error_handling.yaml | High | Error handling for missing parameters |
| AT04 | `listFiles` | test_case_04_list_files_happy_path.yaml | Critical | File listing with metadata and links |
| AT05 | `readFile` | test_case_05_read_file_happy_path.yaml | Critical | Full file content retrieval and integrity |
| AT07 | `search_file` | test_case_07_search_file_happy_path.yaml | High | Pattern matching with context lines |
| AT08 | `edit_file` | test_case_08_edit_file_happy_path.yaml | High | Text replacement using OLD/NEW markers |
| AT09 | `appendData` | test_case_09_append_data_happy_path.yaml | High | Appending content to files |
| AT11 | `deleteFile` | test_case_11_delete_file_happy_path.yaml | High | File deletion and removal verification |
| AT12 | `read_multiple_files` | test_case_12_read_multiple_files_happy_path.yaml | High | Batch file retrieval |
| AT13 | `get_file_type` | test_case_13_get_file_type_happy_path.yaml | High | File type detection from content |
| AT14 | `add_file_to_page` (Confluence) | test_case_14_confluence_add_file_to_page_append.yaml | Critical | Add file from artifact to Confluence page (append) |
| AT15 | `add_file_to_page` (Confluence) | test_case_15_confluence_add_file_to_page_prepend.yaml | High | Add file from artifact to Confluence page (prepend) |
| AT16 | `edit_file` | test_case_16_edit_empty_file_edge_case.yaml | High | Empty file edit behavior validation |
| AT17 | `deleteFile` | test_case_17_delete_nonexistent_file_error.yaml | High | Error handling for non-existent file deletion |
| AT18 | `upload_file` (SharePoint) | test_case_18_sharepoint_upload_file_from_artifact.yaml | Critical | Upload file from artifact to SharePoint |
| AT19 | `upload_file` (SharePoint) | test_case_19_sharepoint_upload_file_replace.yaml | High | Upload file with replace option |
| AT20 | `add_attachment_to_list_item` (SharePoint) | test_case_20_sharepoint_add_attachment_from_artifact.yaml | Critical | Add attachment from artifact to SharePoint list item |
| AT21 | `add_attachment_to_list_item` (SharePoint) | test_case_21_sharepoint_add_attachment_replace.yaml | High | Add attachment with replace option |
| AT22 | `add_file_to_case` (TestRail) | test_case_22_testrail_add_file_to_case.yaml | Critical | Attach file from artifact to TestRail test case |

**Total Test Cases: 19**
- Critical: 8 tests (core artifact operations + integrations)
- High: 11 tests (variations, edge cases, and integration scenarios)

## Artifact Toolkit Features

### Bucket Model
- **Bucket-based storage**: Files organized in named buckets
- **Expiration settings**: Configure automatic cleanup with expiration_measure (days/weeks/months) and expiration_value
- **Name sanitization**: Bucket names sanitize underscores to hyphens for safe URLs
- **API integration**: Provides download links for accessing files

### File Operations

#### Create & Copy
- `createFile`: Create files from content OR copy existing files (binary-safe)
- Supports text, JSON, CSV, Excel formats
- Option to preserve binary format when copying

#### Read Operations
- `readFile`: Full file retrieval with optional page/sheet filtering
- `read_multiple_files`: Batch read multiple files in single operation

#### Search & Edit
- `search_file`: Pattern matching (regex or literal) with context lines
- `edit_file`: Precise text replacement using OLD/NEW marker pairs
- Support for multiple edits per operation

#### Append
- `appendData`: Append content to file (create if missing with flag control)

#### Management
- `deleteFile`: Delete with existence validation
- `listFiles`: List bucket contents with metadata (name, size, modified, download link)
- `get_file_type`: Detect file type from magic bytes (more reliable than extension)

### File Type Support
- **Text**: .txt, .md, .log, .csv, .json, .yaml
- **Spreadsheet**: .xlsx, .xls, .csv with sheet/data filtering
- **Binary**: Supports copy mode for format-preserving operations
- **Detection**: Uses magic bytes for reliable type identification

## Test Execution

### Prerequisites

1. **Environment Configuration** (`.env`):
```bash
# Platform connection
DEPLOYMENT_URL=https://your-deployment.elitea.ai
API_KEY=your_api_key
PROJECT_ID=your_project_id

# SDK LLM
OPENAI_API_KEY=sk-...

# Optional: Artifact configuration
ARTIFACT_TOOLKIT_ID=auto-created-by-setup
TEST_BUCKET=auto-created-by-setup

# For integration tests (Confluence, SharePoint, TestRail)
CONFLUENCE_API_KEY=your_confluence_api_key
CONFLUENCE_USERNAME=your_username
SHAREPOINT_CLIENT_SECRET=your_sharepoint_secret
TESTRAIL_USERNAME=your_testrail_username
TESTRAIL_PASSWORD=your_testrail_password
```

2. **Setup artifacts** (created automatically by pipeline):
   - Artifact toolkit instance
   - Test bucket with expiration settings
   - Confluence toolkit (for AT14-AT15)
   - SharePoint toolkit (for AT18-AT21)
   - TestRail toolkit (for AT22)
   - Test artifact files for integration tests

### Running Tests

```bash
# Run all artifact toolkit tests
cd .alita/tests/test_pipelines
./run_test.sh suites/artifact_toolkit

# Run specific test
./run_test.sh suites/artifact_toolkit test_case_01

# Local execution (no backend)
./run_test.sh --local suites/artifact_toolkit

# Full workflow (setup + run + cleanup)
./run_test.sh --all suites/artifact_toolkit
```

### Test Isolation

All tests are independent and use only artifacts created in the pipeline setup stage:
- `${ARTIFACT_TOOLKIT_ID}`: Created by setup step
- `${TEST_BUCKET}`: Created by setup step
- `${TIMESTAMP}`: Unique identifier for test runs

Each test creates its own test data, avoiding collisions and dependencies.

## Legacy Test Mapping

This suite is derived from legacy artifact test specifications (TC-001 through TC-010):

| Legacy | Tool | New Test | Status |
|--------|------|----------|--------|
| TC-001 | CreateBucket | AT01 | ✅ Implemented |
| TC-002 | CreateFile | AT02, AT03 | ✅ Implemented |
| TC-003 | ListFiles | AT04 | ✅ Implemented |
| TC-004 | ReadFile | AT05 | ✅ Implemented |
| TC-005 | ReadFileChunk | AT06 | ✅ Implemented |
| TC-006 | SearchFile | AT07 | ✅ Implemented |
| TC-007 | EditFile | AT08 | ✅ Implemented |
| TC-008 | ReadMultipleFiles | AT12 | ✅ Implemented |
| TC-009 | AppendData | AT09 | ✅ Implemented |
| TC-010 | DeleteFile | AT11 | ✅ Implemented |
| N/A | GetFileType | AT13 | ✅ Additional |

## Test File Structure

Each test file follows the standard 2-node pattern:

### Node 1: Toolkit Execution
```yaml
- name: invoke_<tool>
  node_type: toolkit
  toolkit_id: ${ARTIFACT_TOOLKIT_ID}
  tool_name: <tool_name>
  tool_params:
    <param>: ${<param>}
  output_key: tool_result
  next: validate_result
```

### Node 2: LLM Validation
```yaml
- id: validate_result
  type: llm
  model: gpt-4o-2024-11-20
  input:
    - tool_result
  input_mapping:
    system:
      type: fixed
      value: "You are a QA validator..."
    task:
      type: fstring
      value: |
        [Validation logic]
        Return JSON: {test_passed, summary, error}
  transition: END
```

## Setup & Cleanup

### Setup Phase (Automatic)
1. **Create Artifact Toolkit**
   - Type: `artifact`
   - Saves toolkit ID to `ARTIFACT_TOOLKIT_ID`

2. **Create Test Bucket**
   - Bucket name: `test-bucket-{{ TIMESTAMP }}`
   - Expiration: 2 weeks
   - Saves bucket name to `TEST_BUCKET`

### Cleanup Phase (Automatic)
1. Remove all AT* pipeline instances
2. Delete artifact toolkit instance
3. Clean up test bucket

## Validation Strategy

### Critical Tests (AT01, AT02, AT04, AT05)
- **Focus**: Core functionality validation
- **Approach**: Verify basic operation succeeds with correct output
- **Failure Criteria**: Missing data, errors, or unexpected behavior

### High Tests (AT03, AT06-AT13)
- **Focus**: Real-world variations and error handling
- **Approach**: Validate variations, edge cases, and error scenarios
- **Error Handling Tests** (AT03): Verify expected errors for invalid input
  - Expected errors (invalid input handling) = test PASSES
  - System errors (unexpected failures) = test FAILS

## Common Issues & Solutions

### Issue: Bucket Already Exists
- **Cause**: Previous run's cleanup didn't complete
- **Solution**: Use unique timestamps in bucket names; setup handles with continue_on_error

### Issue: File Not Found
- **Cause**: Incorrect file path or bucket name
- **Solution**: Tests use setup-created artifacts; verify ${TEST_BUCKET} substitution

### Issue: Edit Not Applied
- **Cause**: OLD marker text doesn't match exactly (case, whitespace)
- **Solution**: Review file_query markers; use exact text from file

### Issue: Search Returns No Matches
- **Cause**: Pattern case sensitivity or regex escaping
- *Integration Tests

### Confluence Integration (AT14-AT15)
Tests artifact → Confluence workflow using `add_file_to_page` tool:
- Upload file from artifact storage to Confluence
- Validate file attachment and page content update
- Test append and prepend positioning options

### SharePoint Integration (AT18-AT21)
Tests artifact → SharePoint workflow using `upload_file` and `add_attachment_to_list_item` tools:
- Upload files from artifact to SharePoint document library
- Attach files from artifact to SharePoint list items
- Test replace/overwrite scenarios

### TestRail Integration (AT22)
Tests artifact → TestRail workflow using `add_file_to_case` tool:
- Attach files from artifact storage to TestRail test cases
- Self-contained test with case creation and cleanup
- Validates end-to-end file attachment flow

## Future Extensions

Potential test additions:
- File copy operations (binary preservation)
- Excel sheet filtering
- CSV parsing with headers
- Large file handling (>10MB)
- Concurrent operations
- Permission/access control
- Bucket expiration cleanup
- File versioning/history
- Additional integration tests (JIRA, GitLab, etc.)
## Future Extensions

Potential test additions:
- File copy operations (binary preservation)
- Excel sheet filtering
- CSV parsing with headers
- Large file handling (>10MB)
- Concurrent operations
- Permission/access control
- Bucket expiration cleanup
- File versioning/history

## Related Documentation

- **Toolkit Implementation**: `alita_sdk/runtime/tools/artifact.py`
- **Configuration Schema**: `alita_sdk/configurations/artifact.py` (if exists)
- **Test Framework**: `.alita/tests/test_pipelines/README.md`
- **Legacy Specs**: `.alita/tests/testcases/artifact/*.md`

## Test Creation History

### Initial Creation
- **Date**: [TIMESTAMP]
- **Request**: Convert legacy artifact tests to new YAML format
- **Source**: TC-001 through TC-010 specifications
- **Tools Discovered**: 13 toolkit operations
- **Test Files Created**: 13 YAML test cases
- **Coverage**: All major artifact toolkit operations

### Modifications
(Track any updates to test suite here)

---

**Suite Status**: ✅ Ready for execution

For test execution instructions, see `.alita/tests/test_pipelines/README.md`
