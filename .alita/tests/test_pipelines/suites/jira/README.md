# JIRA Toolkit Test Suite

This directory contains a test suite for validating JIRA toolkit functionality through the Alita SDK.

## Directory Structure

```
jira_toolkit/
├── pipeline.yaml          # Main suite configuration
├── tests/                 # Test case files
│   └── test_case_01_search_issues.yaml
└── README.md
```

## Prerequisites

1. **JIRA Credentials** - Set the following environment variables in `.env`:
   ```bash
   JIRA_BASE_URL=https://your-instance.atlassian.net
   JIRA_USERNAME=your-email@example.com
   JIRA_API_KEY=your-api-key-or-token
   JIRA_PROJECT_KEY=TEST
   ```

2. **For Cloud instances** - Use username + API key authentication
3. **For Server/DC instances** - Use personal access token

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

# Run tests
./run_test.sh jira_toolkit case_01
```

## Test Cases

### JR01 - Search Issues by JQL
**File:** `tests/test_case_01_search_issues.yaml`

Tests the `search_issues` tool by executing a JQL query and validating:
- Tool returns results
- Results contain issue keys from the expected project
- Proper parsing of issue data

**JQL Used:** `project = ${JIRA_PROJECT_KEY} ORDER BY created DESC`

## Configuration

### jira-config.json
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
