# List Pull Request Diffs

## Objective

Verify that the `list_pull_request_diffs` tool correctly retrieves the file changes (diffs) for a specific pull request from a GitHub repository, including file paths, patches, status, and change statistics.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Repository** | `VladVariushkin/agent` | Target GitHub repository (owner/repo format) |
| **Access Token** | `GIT_TOOL_ACCESS_TOKEN` | GitHub personal access token for authentication |
| **Base URL** | `https://api.github.com` | GitHub API endpoint |
| **Tool** | `list_pull_request_diffs` | GitHub tool to execute for retrieving PR diffs |
| **PR Number** | `9` | The pull request number to retrieve diffs for |

## Pre-requisites

- The target repository exists and is accessible
- Valid GitHub access token with appropriate permissions for the target repository
- The testing environment has network access to GitHub API
- Pull request #9 exists in the repository with file changes

## Config

path: .github\ai_native\testcases\configs\git-config.json

## Test Steps & Expectations

### Step 1: Execute the Tool

Execute the `list_pull_request_diffs` tool with PR number `9` against the target repository.

**Expectation:** The tool runs without errors and returns a list of file changes with diff information.

### Step 2: Verify Output Content

Review the tool's output to ensure it contains the expected diff details.

**Expectation:** The output is a list containing file diff objects. Each diff object should have fields including `path`, `filename`, `status`, `additions`, `deletions`, and `changes`. At least one file should show `status` as `modified` or `added`. The output should contain diff information for files like `.gitignore`, `README.md`, or `requirements.txt`.

## Final Result

- ✅ **Pass:** If all expectations are met throughout the test steps, the objective is achieved and the test passes
- ❌ **Fail:** If any expectation fails at any point, the test fails
