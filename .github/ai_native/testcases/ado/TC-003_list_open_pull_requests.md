# List Open Pull Requests

## Objective

Verify that the `list_open_pull_requests` tool correctly retrieves a list of open pull requests from the Azure DevOps repository.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Organization URL** | `${ADO_ORGANIZATION_URL}` | Azure DevOps organization URL |
| **Project** | `${ADO_PROJECT}` | Azure DevOps project name |
| **Repository ID** | `${ADO_REPOSITORY_ID}` | Azure DevOps repository ID |
| **Token** | `${ADO_TOKEN}` | Azure DevOps personal access token |
| **Base Branch** | `main` | Base branch name |
| **Active Branch** | `main` | Active branch name |
| **Tool** | `list_open_pull_requests` | ADO repos tool to execute for listing open pull requests |

## Config

path: .alita\tool_configs\ado-config.json
generateTestData : false

## Pre-requisites

- Azure DevOps organization and project exist and are accessible
- Valid Azure DevOps personal access token with read permissions
- Repository with ID specified in config exists
- Repository may contain open pull requests

## Test Steps & Expectations

### Step 1: Execute the Tool

Execute the `list_open_pull_requests` tool to retrieve open pull requests from the repository.

**Expectation:** The tool runs without errors and returns a list of open pull requests.

### Step 2: Verify the Output

Verify that the output contains the expected pull requests information.

**Expectation:** The output contains a list of open pull requests with their details (ID, title, source branch, target branch, etc.).
