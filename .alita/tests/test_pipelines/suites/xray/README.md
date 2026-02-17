# Xray Cloud Toolkit Test Suite

This test suite validates the functionality of the Xray Cloud toolkit integration with the Alita SDK.

## Overview

The Xray Cloud toolkit provides comprehensive test management capabilities including test case creation, test retrieval via JQL queries, custom GraphQL execution, and attachment management for test steps.

## Test Coverage

### GraphQL Query Operations (XR01-XR02)
- **XR01**: Execute custom GraphQL query
- **XR02**: Get tests by JQL query

### Test Creation Operations (XR03-XR04, XR07, XR09)
- **XR03**: Create Manual test with steps
- **XR04**: Create Generic test with unstructured definition
- **XR07**: Create multiple tests in batch (Manual + Generic)
- **XR09**: Create Cucumber test with Gherkin BDD syntax

### Attachment Operations (XR05-XR06)
- **XR05**: Get test step attachments
- **XR06**: Add attachment to test step

### Error Handling & Negative Tests (XR10-XR12)
- **XR10**: Invalid step_id error handling (negative test)
- **XR11**: Non-existent test error handling (negative test)
- **XR12**: Invalid JQL syntax error handling (negative test)

## Configuration

### Required Environment Variables

Set the following environment variables in your `.env` file:

```bash
# Xray Cloud Configuration
XRAY_CLIENT_ID=<your_xray_client_id>
XRAY_CLIENT_SECRET=<your_xray_client_secret>
XRAY_PROJECT_KEY=<your_jira_project_key>

# Optional: Override default values
XRAY_BASE_URL=https://xray.cloud.getxray.app
XRAY_CONFIG_PATH=../../configs/xray-config.json
XRAY_TOOLKIT_NAME=xray-testing
```

### Config File Location

The toolkit configuration file is located at:
```
.alita/tests/test_pipelines/configs/xray-config.json
```

## Running Tests

### Run All Tests
```bash
bash .alita/tests/test_pipelines/run_all_suites.sh -v suites/xray
```

### Run Individual Test
```bash
bash .alita/tests/test_pipelines/run_test.sh --seed --setup suites/xray XR01
```

### Run Specific Test Range
```bash
# Run tests XR01 through XR04
bash .alita/tests/test_pipelines/run_test.sh --seed --setup suites/xray XR01-XR04

# Run all positive tests (XR01-XR09)
bash .alita/tests/test_pipelines/run_test.sh --seed --setup suites/xray XR01-XR09

# Run negative tests only (XR10-XR12)
bash .alita/tests/test_pipelines/run_test.sh --seed --setup suites/xray XR10-XR12
```

## Test Data

Tests generate unique test data using timestamps and random suffixes to avoid conflicts:
- Test cases: `"XR{XX} Manual Test {timestamp}-{suffix}"`
- Test identifiers: Based on test execution timestamp

## Test Dependencies

### Test Execution Order
1. **XR01-XR02**: GraphQL operations (independent, can run first)
2. **XR03-XR04, XR07, XR09**: Test creation (creates test data for attachment tests)
3. **XR05-XR06**: Attachment operations (depends on test data from XR03)
4. **XR10-XR12**: Negative tests (error handling validation, independent)

### Data Dependencies
- XR05 and XR06 assume that XR03 created a Manual test with steps
- Tests retrieve test IDs dynamically from Xray API

## Authentication

Xray Cloud uses OAuth2 authentication with client credentials:
- `client_id` and `client_secret` are used to obtain a JWT token
- Token is automatically refreshed as needed
- Authentication is handled transparently by the toolkit

## GraphQL Support

The Xray toolkit supports both:
1. **JQL Queries**: Standard Jira Query Language for retrieving tests
2. **Custom GraphQL**: Advanced queries and mutations for complex operations

### GraphQL Examples

**Query Tests:**
```graphql
query {
  getTests(jql: "project = \"CALC\"", limit: 10, start: 0) {
    results {
      issueId
      jira(fields: ["key", "summary"])
      testType { name }
    }
  }
}
```

**Create Manual Test:**
```graphql
mutation {
  createTest(
    testType: { name: "Manual" },
    steps: [
      { action: "Step 1", result: "Expected result 1" }
    ],
    jira: {
      fields: {
        summary: "Test Summary",
        project: { key: "CALC" }
      }
    }
  ) {
    test {
      issueId
      jira(fields: ["key"])
    }
  }
}
```

## Known Limitations

1. **Step IDs**: Adding attachments requires step UUIDs, not test issue keys
2. **File Size**: Large attachments may impact test execution time
3. **Project Access**: Tests require appropriate Jira/Xray project permissions

## Troubleshooting

### Authentication Errors
- Verify `XRAY_CLIENT_ID` and `XRAY_CLIENT_SECRET` are correct
- Check that credentials have access to the specified project

### GraphQL Errors
- Validate GraphQL syntax using Xray's GraphQL explorer
- Ensure all required fields are included in queries/mutations

### Test Creation Failures
- Verify `XRAY_PROJECT_KEY` exists and is accessible
- Check that test type names match Xray configuration (case-sensitive)

## References

- [Xray Cloud API Documentation](https://docs.getxray.app/display/XRAYCLOUD/REST+API)
- [Xray GraphQL API](https://docs.getxray.app/display/XRAYCLOUD/GraphQL+API)
- [Alita SDK Toolkit Documentation](../../../../docs/tools/)
