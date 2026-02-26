# TestRail Toolkit Test Suite

Test suite for TestRail toolkit under `alita_sdk/tools/testrail/`.

## Overview

This test suite validates the functionality of the TestRail toolkit, which provides integration with TestRail test management platform for managing test cases, suites, and attachments.

## Test Coverage

| Tool | Test Files | Priority | Status |
|------|------------|----------|--------|
| get_case | test_case_01, test_case_02 | Critical, High | ✅ Created |
| get_cases | test_case_03, test_case_04 | Critical, High | ✅ Created |
| get_cases_by_filter | test_case_05, test_case_06 | Critical, High | ✅ Created |
| add_case | test_case_07, test_case_08 | Critical, High | ✅ Created |
| add_cases | test_case_09, test_case_10 | Critical, High | ✅ Created |
| update_case | test_case_11, test_case_12 | Critical, High | ✅ Created |
| add_file_to_case | test_case_13, test_case_14 | High | ✅ Created (Critical test moved to Artifact suite) |
| get_suites | test_case_15, test_case_16 | Critical, High | ✅ Created |

**Total:** 8 tools covered, 15 test files (Critical file attachment test migrated to Artifact suite as ART22)

## Test Scenarios

### TR01-TR02: get_case
- **TR01** (Critical): Retrieve single test case by ID - happy path
- **TR02** (High): Error handling for invalid/non-existent test case ID

### TR03-TR04: get_cases
- **TR03** (Critical): Retrieve all test cases for a project in JSON format
- **TR04** (High): Test multiple output formats (CSV, Markdown)

### TR05-TR06: get_cases_by_filter
- **TR05** (Critical): Filter test cases by type_id
- **TR06** (High): Filter with custom field selection (keys parameter)

### TR07-TR08: add_case
- **TR07** (Critical): Create new test case with basic properties (template_id: 1)
- **TR08** (High): Create test case with custom_steps_separated format (template_id: 2)

### TR09-TR10: add_cases
- **TR09** (Critical): Bulk create multiple test cases
- **TR10** (High): Create test case with minimal/default properties

### TR11-TR12: update_case
- **TR11** (Critical): Update multiple fields of existing test case
- **TR12** (High): Partial update (single field) of test case

### TR13-TR14: add_file_to_case
- **TR13** (High): Error handling for non-existent artifact file
- **Note**: Critical file attachment test (happy path) moved to Artifact suite as ART22

### TR15-TR16: get_suites
- **TR15** (Critical): Retrieve test suites for a project in JSON format
- **TR16** (High): Test multiple output formats (Markdown)

## Setup Artifacts

The pipeline.yaml setup stage creates the following artifacts before tests run:

- **Toolkit Instance**: `${TESTRAIL_TOOLKIT_ID}` - TestRail toolkit configured with credentials
- **Test Case**: `${TESTRAIL_TEST_CASE_ID}` - Test case created for read/update operations

## Environment Variables

Required variables (set in `.alita/tests/test_pipelines/.env`):

### Credentials (Required)
- `TESTRAIL_URL`: TestRail instance URL (e.g., `https://your-instance.testrail.io`)
- `TESTRAIL_EMAIL`: User email for authentication
- `TESTRAIL_PASSWORD`: Password or API key

### Project Configuration (Required)
- `TESTRAIL_PROJECT_ID`: TestRail project ID for testing
- `TESTRAIL_SECTION_ID`: Section ID where test cases will be created

### Optional Configuration
- `TESTRAIL_SUITE_ID`: Suite ID (for multi-suite mode projects)
- `TESTRAIL_SECRET_NAME`: Configuration secret name (default: `testrail`)
- `TESTRAIL_TOOLKIT_NAME`: Toolkit name (default: `testrail-testing`)
- `TESTRAIL_CONFIG_PATH`: Config file path (default: `../../configs/testrail-config.json`)

## Running Tests

### Run all tests
```bash
cd .alita/tests/test_pipelines
./run_test.sh --local suites/testrail
```

### Run specific test
```bash
./run_test.sh --local suites/testrail TR01
```

### Run tests in Docker
```bash
./run_test.sh suites/testrail
```

## Test Isolation

All tests are designed to be independent:
- Tests use ONLY artifacts created in the setup stage
- No test depends on execution order
- Each test validates one specific tool operation
- Cleanup stage removes all created resources

## Suite Configuration

- **Suite Mode Support**: Tests handle both single-suite and multi-suite project modes
- **Template Support**: Tests cover both template_id 1 (simple steps) and 2 (separated steps)
- **Output Formats**: Tests validate JSON, CSV, and Markdown output formats
- **Error Handling**: High-priority tests validate proper error handling for invalid inputs

## Notes

- The TestRail toolkit requires valid credentials and an active TestRail instance
- Test case creation tests (TR07-TR10) will create actual test cases in the configured section
- File attachment error handling test (TR13) validates proper error messages for missing files
- **File attachment happy path** (artifact upload) is tested in Artifact suite as ART22
- Some tests may fail if the TestRail project is in multi-suite mode without TESTRAIL_SUITE_ID set

## Test Creation History

### Run: 2026-02-24

- **Request**: Create tests for testrail toolkit using ado, bitbucket, github as examples
- **Tools discovered**: 8 (get_case, get_cases, get_cases_by_filter, add_case, add_cases, update_case, add_file_to_case, get_suites)
- **Test files created**: 16 (2 per tool: Critical + High)
- **Test files skipped**: 0 (no duplicates)
- **Config created**: Yes (testrail-config.json, pipeline.yaml)
- **Suite structure**: New suite created from scratch

## Related Documentation

- TestRail API Documentation: https://support.testrail.com/hc/en-us/articles/7077196481428-API-Reference
- Toolkit Implementation: [alita_sdk/tools/testrail/](../../../../alita_sdk/tools/testrail/)
- Configuration Schema: [alita_sdk/configurations/testrail.py](../../../../alita_sdk/configurations/testrail.py)
