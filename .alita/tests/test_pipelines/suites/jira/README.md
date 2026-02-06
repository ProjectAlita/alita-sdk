# JIRA Toolkit Test Suite

Test suite for JIRA toolkit under `alita_sdk/tools/jira/`.

## Directory Structure

```
jira/
├── pipeline.yaml          # Suite configuration
├── tests/                 # Test case files (28 tests)
│   ├── test_case_01_search_using_jql_happy_path.yaml
│   ├── test_case_02_search_using_jql_no_results.yaml
│   └── ... (26 more tests)
└── README.md
```

## Test Coverage

| Tool | Test Files | Priority | Status |
|------|------------|----------|--------|
| search_using_jql | test_case_01, test_case_02 | Critical | ✅ Created |
| create_issue | test_case_03, test_case_04 | Critical | ✅ Created |
| update_issue | test_case_05, test_case_06 | Critical | ✅ Created |
| modify_labels | test_case_07, test_case_08 | Critical | ✅ Created |
| list_comments | test_case_09, test_case_10 | Critical | ✅ Created |
| add_comments | test_case_11, test_case_12 | Critical | ✅ Created |
| list_projects | test_case_13, test_case_14 | Critical | ✅ Created |
| set_issue_status | test_case_15, test_case_16 | Critical | ✅ Created |
| get_specific_field_info | test_case_17, test_case_18 | High | ✅ Created |
| get_field_with_images | test_case_19, test_case_20 | High | ✅ Created |
| get_comments_with_images | test_case_21, test_case_22 | High | ✅ Created |
| geFull Suite Execution

```bash
cd /path/to/alita-sdk/.alita/tests/test_pipelines

# Run all tests with full workflow
./run_all_suites.sh jira

# Run specific test
./run_test.sh --all suites/jira jr01
```

### Individual Test Execution

```bash
# Run with setup and seed
./run_test.sh --setup --seed suites/jira jr01

# Run specific test (after setup)
./run_test.sh suites/jira jr01

# Run test range
./run_test.sh suites/jira "jr0[1-5]"

# Verbose output
./run_test.sh -v suites/jira jr01
```

### Local Execution (No Backend)

```bash
# Run locally without platform
./run_test.sh --local suites/jira jrersonal access token

## Running the Suite

### Local Execution (No Backend Required)

```bash
cd /path/to/alita-sdk/.alita/tests/test_pipelines

# Run specific test
python run_test.py --local jira_toolkit search_issues

# Run all tests
python run_test.py --local jira_toolkit "*"

# Verbose output
python run_test.py --local jira_toolkit search_issues -v
```

### Remote Execution (With Backend)

```bash
# Setup toolkit on backend
python scripts/setup.py jira_toolkit

# Seed pipelines
python scripts/seed_pipelines.py jira_toolkit
search_using_jql (JR01-JR02)
- **JR01**: Happy path - search with results
- **JR02**: Edge case - search with no results (empty result set)

### create_issue (JR03-JR04)
- **JR03**: Happy path - create issue with required fields
- **JR04**: Edge case - create issue with invalid project

### update_issue (JR05-JR06)
- **JR05**: Happy path - update existing issue
- **JR06**: Edge case - update nonexistent issue

### modify_labels (JR07-JR08)
- **JR07**: Happy path - add labels to issue
- **JR08**: Edge case - remove labels from issue

### list_comments (JR09-JR10)
- *Pipeline Setup

The test suite performs the following setup steps:

1. **JIRA Configuration**: Creates secret with API credentials
2. **JIRA Toolkit**: Creates/updates toolkit with base configuration
3. **Test Issue 1**: Retrieves first issue from project (for read/update operations)
4. **Test Issue 2**: Retrieves second issue from project (for linking operations)

This ensures tests have existing issues to work with for read/update/link operations.

## Configuration

The suite uses `configs/jira-config.json` which defines:
- Base URL and authentication
- Cloud/Server mode
- API version
- Available tools and their configurations
### get_field_with_images (JR19-JR20)
- **JR19**: Happy path - get field containing images
- **JR20**: Edge case - get field from invalid issue

### get_comments_with_images (JR21-JR22)
- **JR21**: Happy path - retrieve comments with embedded images
- **JR22**: Edgetool_name_scenario.yaml
   ```

2. Use the toolkit reference structure:
   ```yaml
   toolkits:
     - id: ${JIRA_TOOLKIT_ID}
       name: ${JIRA_TOOLKIT_NAME}
   ```

3. Define nodes using toolkit type with the JIRA tool

4. Available test variables:
   - `${JIRA_TOOLKIT_ID}` - Toolkit ID
   - `${JIRA_TOOLKIT_NAME}` - Toolkit name
   - `${JIRA_PROJECT}` - Project key
   - `${JIRA_TEST_ISSUE}` - First test issue key
   - `${JIRA_TEST_ISSUE_2}` - Second test issue key
   - `${TIMESTAMP}` - Current timestamp

## Notes

- All test validations are derived from actual tool implementations
- Tests use existing issues from the configured JIRA project
- Write operations (create/update) use timestamp-based unique identifiers
- Test isolation: Each test uses only setup artifacts, no cross-test dependencies
Located at `../configs/jira-config.json`, this file defines:
- Base URL
- Cloud/Server mode
- API version
- Selected tools

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `JIRA_BASE_URL` | JIRA instance URL | Required |
| `JIRA_USERNAME` | JIRA username | Required for Cloud |
| `JIRA_API_KEY` | API key/token | Required |
| `JIRA_PROJECT_KEY` | Project key for tests | `TEST` |
| `JIRA_CLOUD` | Cloud instance? | `true` |
| `JIRA_API_VERSION` | REST API version | `3` |

## Adding New Tests

1. Create a new YAML file in `tests/` following the naming convention:
   ```
   test_case_XX_description.yaml
   ```

2. Use the toolkit reference structure:
   ```yaml
   toolkits:
     - id: ${JIRA_TOOLKIT_ID}
       name: ${JIRA_TOOLKIT_NAME}
   ```

3. Define nodes using toolkit or code types

4. Add the test pattern to `pipeline.yaml` in the `execution.order` section

## Available JIRA Tools

- `search_issues` - Search issues using JQL
- `get_issue` - Get a single issue by key
- `create_issue` - Create a new issue
- `update_issue` - Update an existing issue
- `add_comment` - Add a comment to an issue
- `set_issue_status` - Transition issue status
- `get_projects` - List available projects
- `jira_request` - Generic JIRA API request