# QTest Toolkit Test Suite

This test suite validates the QTest toolkit integration with the Alita SDK.

## Test Coverage

### Search Operations (QT01-QT02)
- **QT01**: `search_by_dql` - DQL search for test cases
- **QT02**: `get_all_test_cases_fields_for_project` - Retrieve field definitions

### Test Case CRUD Operations (QT03-QT05, QT09)
- **QT03**: `create_test_cases` - Create a new test case
- **QT04**: `find_test_case_by_id` - Retrieve test case by ID
- **QT05**: `update_test_case` - Update existing test case
- **QT09**: `delete_test_case` - Delete test case by QTest ID

### Module Operations (QT06)
- **QT06**: `get_modules` - Retrieve module hierarchy

### Attachment Operations (QT07)
- **QT07**: `add_file_to_test_case` - Upload file to test case

### Relationship Operations (QT08, QT10-QT12)
- **QT08**: `find_test_cases_by_requirement_id` - Find test cases linked to requirement
- **QT10**: `link_tests_to_qtest_requirement` - Link test cases to QTest requirement
- **QT11**: `find_requirements_by_test_case_id` - Find requirements linked to test case
- **QT12**: `find_test_runs_by_test_case_id` - Find test runs for test case

### Error Handling & Negative Tests (QT13-QT15)
- **QT13**: Invalid DQL syntax error handling (negative test)
- **QT14**: Non-existent test case error handling (negative test)
- **QT15**: Invalid field values validation (negative test)

## Prerequisites

Before running these tests, ensure:

1. **QTest Instance**: Access to a QTest instance
2. **API Token**: Valid QTest API token with appropriate permissions
3. **Project**: A test project with:
   - At least one existing test case for search tests
   - At least one requirement for relationship tests
   - Permissions to create/update/delete test cases

## Environment Variables

Required environment variables:

```bash
QTEST_BASE_URL=https://your-instance.qtestnet.com
QTEST_API_TOKEN=your_api_token
QTEST_PROJECT_ID=1
QTEST_SECRET_NAME=qtest  # Optional, defaults to 'qtest'
QTEST_TOOLKIT_NAME=qtest-testing  # Optional, defaults to 'qtest-testing'
```

## Running Tests

### Run All Tests
```bash
bash .alita/tests/test_pipelines/run_all_suites.sh -v suites/qtest
```

### Run Specific Test
```bash
bash .alita/tests/test_pipelines/run_test.sh --all -v suites/qtest QT01
```

### Run Test Locally (without cleanup)
```bash
bash .alita/tests/test_pipelines/run_test.sh --local -v suites/qtest QT03
```

### Run Test Range
```bash
# Run all positive tests (QT01-QT12)
bash .alita/tests/test_pipelines/run_test.sh --all -v suites/qtest QT01-QT12

# Run negative tests only (QT13-QT15)
bash .alita/tests/test_pipelines/run_test.sh --all -v suites/qtest QT13-QT15
```

## Test Data

The tests use dynamic data generation with timestamps and random suffixes to avoid conflicts.

## Test Execution Order

1. **QT01-QT02**: Search and field operations (independent, can run first)
2. **QT03-QT09**: CRUD operations (create, read, update, delete)
3. **QT10-QT12**: Relationship operations (requires existing test data)
4. **QT13-QT15**: Negative tests (error handling validation, independent)

## Known Limitations

- Tests require an active QTest instance
- Some tests create test cases that need manual cleanup if tests fail
- DQL searches cannot query by linked objects (requirements, defects) - specialized tools are used instead
