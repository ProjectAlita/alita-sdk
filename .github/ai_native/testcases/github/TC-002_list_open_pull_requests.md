# List Open Pull Requests Tool Functionality

## Objective

Verify that the `list_open_pull_requests` tool correctly retrieves and displays all open pull requests from a GitHub repository, including their titles, numbers, and authors.

## Test Data Configuration

### GitHub Repository Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Repository** | `VladVariushkin/agent` | Target GitHub repository (owner/repo format) |
| **Access Token** | `GIT_TOOL_ACCESS_TOKEN` | GitHub personal access token for authentication |
| **Base URL** | `https://api.github.com` | GitHub API endpoint |
| **Tool** | `list_open_pull_requests` | GitHub tool to execute for listing open PRs |

## Config

path: .github\ai_native\testcases\github\configs\git-config.json

## Pre-requisites

- The target repository exists and is accessible
- Valid GitHub access token with appropriate permissions for the target repository
- Create a test pull request with any title and store its PR number as `{{TEST_PR_NUMBER}}` and title as `{{TEST_PR_TITLE}}` in the repository, you can put any dummy file as a PR content. 
- You may create dummy branch for the PR if needed.
- Pr should be created towards main branch.
- The created pull request must remain open for the test execution.
- Create only one PR for this test to avoid confusion.

## Test Steps & Expectations

### Step 1: Execute the Tool

Execute the `list_open_pull_requests` tool against the target repository.

**Expectation:** The tool runs without errors and returns data about open pull requests.

### Step 2: Verify Output Structure

Review the tool's output to ensure it contains the expected pull request.

**Expectation:** The output contains pull request number `{{TEST_PR_NUMBER}}` The output contains title `{{TEST_PR_TITLE}}` Exactly all expectations must match
Variables like `{{TEST_PR_NUMBER}}` and `{{TEST_PR_TITLE}}` should be replaced with actual values during test execution from your context

## Final Result

- ✅ **Pass:** If all expectations are met throughout the test steps, the objective is achieved and the test passes
- ❌ **Fail:** If any expectation fails at any point, the test fails
