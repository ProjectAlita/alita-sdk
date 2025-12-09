# List Projects

## Objective

Verify that the `list_projects` tool correctly retrieves a list of projects from the Jira instance.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Base URL** | `${CONFLUENCE_BASE_URL}` | Jira instance base URL |
| **Username** | `${CONFLUENCE_USERNAME}` | Jira username/email |
| **API Key** | `${CONFLUENCE_API_KEY}` | Jira API token |
| **Cloud** | `${JIRA_CLOUD}` | Whether using Jira Cloud (true/false) |
| **Tool** | `list_projects` | Jira tool to execute for listing projects |

## Config

path: .alita\tool_configs\jira-config.json
generateTestData : false

## Pre-requisites

- Jira instance is accessible and configured
- Valid Jira API token with appropriate permissions
- User has permission to view projects in the Jira instance
- At least one project exists in the Jira instance

## Test Steps & Expectations

### Step 1: Execute the Tool

List all your available tools you have.

Execute the `list_projects` tool to retrieve projects from the Jira instance.

**Expectation:** The tool runs without errors and returns a list of projects with their keys, names, and other relevant details.


### Step 2: Verify the Output

Verify that the output contains the expected file content.

**Expectation:** The output contains such project: id: 10066, key: AT, name: AI tests, type: business