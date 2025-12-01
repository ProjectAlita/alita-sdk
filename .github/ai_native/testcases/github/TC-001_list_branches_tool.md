# List Branches Displays Custom Branch

## Objective

Verify that the `list_branches_in_repo` tool correctly lists all branches in the repository and that the output includes the branch named `hello`.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Repository** | `VladVariushkin/agent` | Target GitHub repository (owner/repo format) |
| **Access Token** | `GIT_TOOL_ACCESS_TOKEN` | GitHub personal access token for authentication |
| **Base URL** | `https://api.github.com` | GitHub API endpoint |
| **Tool** | `list_branches_in_repo` | GitHub tool to execute for listing branches |

## Config

path: .github\ai_native\testcases\github\configs\git-config.json

## Pre-requisites

- A test repository is cloned locally and accessible
- The repository contains at least the default branch (e.g., `main`) and a branch named `hello`
- The testing environment has the necessary permissions and network access to run the tool
- Valid GitHub access token with appropriate permissions for the target repository

## Test Steps & Expectations

### Step 1: Execute the Tool

Execute the `list_branches_in_repo` tool against the target repository.

**Expectation:** The tool runs without errors and returns a textual list of branch names.

### Step 2: Verify Output

Review the tool's output for the presence of branch names.

**Expectation:** The output text contains the branch name `hello`.

## Final Result

- ✅ **Pass:** If all expectations are met throughout the test steps, the objective is achieved and the test passes
- ❌ **Fail:** If any expectation fails at any point, the test fails