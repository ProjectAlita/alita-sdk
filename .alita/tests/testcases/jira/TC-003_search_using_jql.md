# Search Using JQL

## Objective

Verify that the `search_using_jql` tool correctly searches for and retrieves Jira issues using Jira Query Language (JQL).

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Base URL** | `${JIRA_BASE_URL}` | Jira instance base URL |
| **Username** | `${JIRA_USERNAME}` | Jira username/email |
| **API Key** | `${JIRA_API_KEY}` | Jira API token |
| **Cloud** | `${JIRA_CLOUD}` | Whether using Jira Cloud (true/false) |
| **Tool** | `search_using_jql` | Jira tool to execute for searching issues |

### Test Data

The `search_using_jql` tool accepts a JQL (Jira Query Language) query string to search for issues.

**JQL Query:** `priority = High`

This query will search for all issues that have a priority level set to "High".

**Additional JQL Examples:**
- Search by project: `project = PROJ`
- Search by status: `status = "In Progress"`
- Search by assignee: `assignee = currentUser()`
- Combined search: `project = PROJ AND priority = High AND status != Closed`

## Config

path: .alita\tool_configs\jira-config.json
generateTestData : false

## Pre-requisites

- Jira instance is accessible and configured
- Valid Jira API token with appropriate permissions
- User has permission to search and view issues in the Jira instance
- At least one issue with "High" priority exists in the accessible projects
- The configured limit in jira-config.json determines the maximum number of results returned

## Test Steps & Expectations

### Step 1: Execute the Tool

List all your available tools you have.

Execute the `search_using_jql` tool with the JQL query to search for high priority issues.

**Input:**
```
priority = High AND key ~ AT-2
```

**Expectation:** 
- The tool runs without errors
- Issues matching the JQL query are returned
- The response contains a list of issues with "High" priority
- Each issue in the response includes key fields: key, id, projectId, summary, description, assignee, priority, status, url

### Step 2: Verify the Output

Verify that the output contains the expected search results.

**Expectation:** 
- The output message should start with "Found X Jira issues:" where X is the number of matching issues
- If no issues are found, the output should be "No Jira issues found"
- Each returned issue should have priority set to "High"
- The response should include issue details such as:
  - `key`: Issue key (e.g., "PROJ-123")
  - `summary`: Issue title/summary
  - `priority`: Should be "High"
  - `status`: Current issue status
  - `assignee`: Assigned user or "None"
  - `url`: Browseable URL to the issue

### Step 3: Verify Result Limit

Verify that the number of results respects the configured limit.

**Expectation:**
- The number of returned issues should not exceed the `limit` value configured in jira-config.json (default: 5)
- output contains `{'key': 'AT-2', 'id': '12378', 'projectId': '10066', 'summary': 'Test issue created by automated test',
    'description': {'type': 'doc', 'version': 1, 'content': [{'type': 'paragraph', 'content':
    [{'type': 'text', 'text': 'This is a test issue created to verify the create_issue tool functionality'}]}]},
    'created': '2025-12-08', 'assignee': 'None', 'priority': 'High', 'status': 'To Do', 'updated': '2025-12-08T22:26:02.355+0300',
    'duedate': None, 'url': 'https://epamelitea.atlassian.net/browse/AT-2', 'related_issues': {}, '': None}`
