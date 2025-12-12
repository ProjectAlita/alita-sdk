# Create File in Repository

## Objective

Verify that the `create_file` tool correctly creates a new file with specified content in a GitHub repository branch.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Repository** | `ProjectAlita/elitea-testing` | Target GitHub repository (owner/repo format) |
| **Access Token** | `GIT_TOOL_ACCESS_TOKEN` | GitHub personal access token for authentication |
| **Base URL** | `https://api.github.com` | GitHub API endpoint |
| **Tool** | `create_file` | GitHub tool to execute for creating a new file |
| **File Path** | `TEST_FILE_PATH` | The path where the file should be created |
| **File Contents** | `TEST_FILE_CONTENTS` | The content to write to the new file |
| **Active Branch** | `TEST_BRANCH` | The branch where the file will be created (not main/master) |

## Pre-requisites

- The target repository exists and is accessible
- Valid GitHub access token with write permissions for the target repository
- The testing environment has network access to GitHub API
- A non-main branch (e.g., `TEST_BRANCH`) exists for testing
- The file at `TEST_FILE_PATH` does not already exist in the target branch
- The active branch is set to a non-protected branch (not main/master)

## Config

path: .alita\tool_configs\git-config.json
generateTestData: false

## Test Steps & Expectations

### Step 1: Ensure Active Branch is Not Main

Set active branch to a tc-file-ops-2025-12-08 branch, not the main/master branch.

**Expectation:** The active branch should be `tc-file-ops-2025-12-08`. If the active branch is main/master, the tool should return an error message about protected branches.

### Step 2: Execute the Tool

Execute the `create_file` tool with file path `{{CURRENT_TIME}}.aitest.txt` and contents `{{CURRENT_TIME_AND_DATE}}`.

**Expectation:** The tool runs without errors and returns a success message like "Created file {{CURRENT_TIME}}.aitest.txt".