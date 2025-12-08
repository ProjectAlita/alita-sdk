# Read File from Repository

## Objective

Verify that the `read_file` tool correctly retrieves the content of a file from a GitHub repository branch.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Repository** | `ProjectAlita/elitea-testing` | Target GitHub repository (owner/repo format) |
| **Access Token** | `GIT_TOOL_ACCESS_TOKEN` | GitHub personal access token for authentication |
| **Base URL** | `https://api.github.com` | GitHub API endpoint |
| **Tool** | `read_file` | GitHub tool to execute for reading file content |
| **File Path** | `TEST_FILE_PATH` | The path of the file to read |
| **Branch** | `TEST_BRANCH` | The branch to read the file from (optional, defaults to active branch) |
| **Expected Content** | `TEST_FILE_EXPECTED_CONTENT` | The expected content of the file |

## Pre-requisites

- The target repository exists and is accessible
- Valid GitHub access token with read permissions for the target repository
- The testing environment has network access to GitHub API
- A file exists at `TEST_FILE_PATH` in the repository
- The file has known content that can be verified

## Config

path: .alita\tool_configs\git-config.json
generateTestData: false

## Test Steps & Expectations

### Step 1: Execute the Tool with Default Branch

List all the tools you have

Execute the `read_file` tool from GitHub with file path `.gitignore` using main branch.

**Expectation:** The tool runs without errors and returns the file content as a string.

### Step 2: Verify File Content

Review the returned content to ensure it matches the expected file content.

**Expectation:** The output should be a string containing the file content and should contain .DS_Store and !test-data/sample-*