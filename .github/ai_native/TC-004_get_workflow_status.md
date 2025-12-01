# Get Workflow Status Details

## Objective

Verify that the `get_workflow_status` tool correctly retrieves detailed information about a specific workflow run from a GitHub repository, including its status, conclusion, jobs, and other metadata.

## Test Data Configuration

### GitHub Repository Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Repository** | `VladVariushkin/agent` | Target GitHub repository (owner/repo format) |
| **Access Token** | `GIT_TOOL_ACCESS_TOKEN` | GitHub personal access token for authentication |
| **Base URL** | `https://api.github.com` | GitHub API endpoint |
| **Tool** | `get_workflow_status` | GitHub tool to execute for retrieving workflow run details |
| **Run ID** | `15975845513` | The workflow run ID to retrieve |

## Config

path: .github\ai_native\testcases\configs\git-config.json

## Pre-requisites

- The target repository exists and is accessible
- Valid GitHub access token with appropriate permissions for the target repository
- The testing environment has network access to GitHub API
- Workflow run #15975845513 exists in the repository

## Test Steps & Expectations

### Step 1: Execute the Tool

Execute the `get_workflow_status` tool with run ID `15975845513` against the target repository.

**Expectation:** The tool runs without errors and returns detailed information about the workflow run.

### Step 2: Verify Output Content

Review the tool's output to ensure it contains the expected workflow run details.

**Expectation:** The output contains run ID `15975845513`, workflow name `AGENT_TESTS`, status `completed`, conclusion `failure`, head branch `fix-convert-to-bdd-method`, and at least one job with status `completed`.

## Final Result

- ✅ **Pass:** If all expectations are met throughout the test steps, the objective is achieved and the test passes
- ❌ **Fail:** If any expectation fails at any point, the test fails
