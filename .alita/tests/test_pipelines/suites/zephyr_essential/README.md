# Zephyr Essential Toolkit Test Suite

This test suite validates the functionality of the Zephyr Essential (Zephyr Scale) toolkit integration with the Alita SDK.

## Overview

The Zephyr Essential toolkit provides comprehensive test management capabilities including test case management, test cycle management, test execution tracking, and link management for Jira-based test workflows.

## Test Coverage

### Health Check (ZE01)
- **ZE01**: API health check verification

### Project Operations (ZE02-ZE03)
- **ZE02**: List all projects
- **ZE03**: Get specific project details

### Folder Operations (ZE04-ZE07)
- **ZE04**: List folders in a project
- **ZE05**: Create new folder
- **ZE06**: Retrieve folder by ID
- **ZE07**: Find folder by name

### Test Case Operations (ZE08-ZE13)
- **ZE08**: List test cases in a project
- **ZE09**: Create new test case
- **ZE10**: Retrieve test case by key
- **ZE11**: Update existing test case
- **ZE12**: Create test steps for test case
- **ZE13**: Retrieve test steps for test case

### Test Cycle Operations (ZE14-ZE17)
- **ZE14**: List test cycles in a project
- **ZE15**: Create new test cycle
- **ZE16**: Retrieve test cycle by key
- **ZE17**: Update existing test cycle

### Test Execution Operations (ZE18-ZE21)
- **ZE18**: List test executions
- **ZE19**: Create new test execution
- **ZE20**: Retrieve test execution by key
- **ZE21**: Update test execution status

### Link Operations (ZE22-ZE24)
- **ZE22**: Create web link for test case
- **ZE23**: Retrieve links for test case
- **ZE24**: Delete link

## Configuration

### Required Environment Variables

Set the following environment variables in your `.env` file:

```bash
# Zephyr Essential Configuration
ZEPHYR_ESENTIALS_KEY=<your_zephyr_essential_api_token>
ZEPHYR_PROJECT_KEY=<your_jira_project_key>
JIRA_PROJECT_ID=<your_jira_project_id>

# Optional: Override default values
ZEPHYR_ESSENTIAL_BASE_URL=https://prod-api.zephyr4jiracloud.com/v2
ZEPHYR_ESSENTIAL_CONFIG_PATH=../../configs/zephyr-essential-config.json
ZEPHYR_ESSENTIAL_TOOLKIT_NAME=zephyr-essential-testing
```

### Config File Location

The toolkit configuration file is located at:
```
.alita/tests/test_pipelines/configs/zephyr-essential-config.json
```

## Running Tests

### Run All Tests
```bash
bash .alita/tests/test_pipelines/run_all_suites.sh -v suites/zephyr_essential
```

### Run Individual Test
```bash
bash .alita/tests/test_pipelines/run_test.sh --seed --setup suites/zephyr_essential ZE01
```

### Run Specific Test Range
```bash
# Run tests ZE01 through ZE07
bash .alita/tests/test_pipelines/run_test.sh --seed --setup suites/zephyr_essential ZE01-ZE07
```

## Test Data

Tests generate unique test data using timestamps and random suffixes to avoid conflicts:
- Test cases: `"Test Case ZE{XX} {timestamp}-{suffix}"`
- Test cycles: `"Test Cycle ZE{XX} {timestamp}-{suffix}"`
- Folders: `"TestFolder-ZE{XX}-{timestamp}-{suffix}"`

## Test Dependencies

Some tests have dependencies on previous operations:
- Test executions require both test cases and test cycles
- Test step operations require an existing test case
- Link retrieval requires a link to be created first

## Notes

1. **API Token**: Obtain a Zephyr Essential API token from your Zephyr Scale configuration in Jira
2. **Project Key**: Use a valid Jira project key where Zephyr Scale is enabled
3. **Project ID**: The numeric Jira project ID (not the key)
4. **Rate Limits**: Zephyr Essential API may have rate limits; tests include appropriate delays
5. **Cleanup**: Test entities (test cases, cycles, etc.) are created but not automatically deleted

## Troubleshooting

### Common Issues

1. **Authentication Errors**: Verify `ZEPHYR_ESENTIALS_KEY` is valid and not expired
2. **Project Not Found**: Ensure `ZEPHYR_PROJECT_KEY` matches an existing Jira project with Zephyr Scale enabled
3. **Permission Errors**: Verify the API token has appropriate permissions for test management operations
4. **Missing Project ID**: Some operations require the numeric Jira project ID, not just the project key

### Debug Mode

Run tests with verbose output:
```bash
bash .alita/tests/test_pipelines/run_test.sh -v --seed --setup suites/zephyr_essential ZE01
```

## References

- [Zephyr Scale API Documentation](https://support.smartbear.com/zephyr-scale-cloud/api-docs/)
- [Alita SDK Documentation](https://github.com/ProjectAlita/alita-sdk)
- [Test Pipeline Framework](../../README.md)
