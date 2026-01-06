# Get Pull Request Details

## Objective

Verify that the `get_pull_request` tool correctly retrieves detailed information about a specific pull request from a GitHub repository, including its title, state, author, and other metadata.

## Test Data Configuration

### GitHub Repository Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Repository** | `ProjectAlita/elitea-testing` | Target GitHub repository (owner/repo format) |
| **Access Token** | `GIT_TOOL_ACCESS_TOKEN` | GitHub personal access token for authentication |
| **Base URL** | `https://api.github.com` | GitHub API endpoint |
| **Tool** | `get_pull_request` | GitHub tool to execute for retrieving PR details |
| **PR Number** | `{{TEST_PR_NUMBER}}` | The pull request number to retrieve |

## Config

path: .alita\tool_configs\git-config.json
generateTestData: false

## Pre-requisites

- The target repository exists and is accessible
- Valid GitHub access token with appropriate permissions for the target repository
- Pull request `{{TEST_PR_NUMBER}}` exists in the repository
- Pull request title is saved to `{{TEST_PR_TITLE}}`

## Test Steps & Expectations

### Step 1: Execute the Tool

Execute the `get_pull_request` tool with PR number `14` against the target repository.

**Expectation:** The tool runs without errors and returns detailed information about the pull request.

### Step 2: Verify Output Content

Review the tool's output to ensure it contains the expected pull request details.

**Expectation:** The output contains PR number `14`, title `AI Testing pull request`.
