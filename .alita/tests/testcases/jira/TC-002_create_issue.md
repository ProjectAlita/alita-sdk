# Create Issue

## Objective

Verify that the `create_issue` tool correctly creates a new issue in the Jira instance.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Base URL** | `${JIRA_BASE_URL}` | Jira instance base URL |
| **Username** | `${JIRA_USERNAME}` | Jira username/email |
| **API Key** | `${JIRA_API_KEY}` | Jira API token |
| **Cloud** | `${JIRA_CLOUD}` | Whether using Jira Cloud (true/false) |
| **Tool** | `create_issue` | Jira tool to execute for creating an issue |
| **Project Key** | `${JIRA_PROJECT_KEY}` | The project key where the issue will be created |


## Config

path: .alita\tool_configs\jira-config.json
generateTestData : false

## Pre-requisites

- Jira instance is accessible and configured
- Valid Jira API token with appropriate permissions
- User has permission to create issues in the specified project
- The project specified by `${JIRA_PROJECT_KEY}` exists and is accessible
- The issue type "Task" is available in the project
- The priority "Major" is configured in the Jira instance

## Test Steps & Expectations

### Step 1: Execute the Tool

List all your available tools you have.

Execute the `create_issue` tool with the test data to create a new issue in the Jira instance.

**Input:**
```json
{"fields": {"project": {"key": "AT"}, "summary": "Test issue created by automated test", "description": {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": "This is a test issue created to verify the create_issue tool functionality"}]}]}, "issuetype": {"name": "Task"}, "priority": {"name": "High"}}}
```

**Note:** The description field uses Atlassian Document Format (ADF), which is required for Jira Cloud API v3. The ADF structure includes:
- `type`: "doc" (the document root)
- `version`: 1 (ADF version)
- `content`: Array of content blocks (paragraphs, headings, lists, etc.)

**Expectation:** 
- The tool runs without errors
- A new issue is successfully created in Jira
- The response includes the created issue key (e.g., "PROJ-123")
- The response includes a URL to view the created issue

### Step 2: Verify the Output

Verify that the output contains confirmation of successful issue creation.

**Expectation:** 
- The output message should contain "Done. Issue [ISSUE-KEY] is created successfully"
- The output should include a browseable URL in the format: `${JIRA_BASE_URL}/browse/[ISSUE-KEY]`
- The output should include issue details confirming the creation