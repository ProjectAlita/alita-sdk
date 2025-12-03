# Get Specific Issue Details

## Objective

Verify that the `get_issue` tool correctly retrieves detailed information about a specific issue from a GitHub repository by its issue number.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Repository** | `VladVariushkin/agent` | Target GitHub repository (owner/repo format) |
| **Access Token** | `GIT_TOOL_ACCESS_TOKEN` | GitHub personal access token for authentication |
| **Base URL** | `https://api.github.com` | GitHub API endpoint |
| **Tool** | `get_issue` | GitHub tool to execute for retrieving specific issue |
| **Issue Number** | `TEST_ISSUE_NUMBER` | The issue number to retrieve details for |

## Pre-requisites

- The target repository exists and is accessible
- Valid GitHub access token with appropriate permissions for the target repository
- The testing environment has network access to GitHub API
- Issue with number `TEST_ISSUE_NUMBER` exists in the repository

## Config

path: .github\ai_native\testcases\configs\git-config.json

## Test Steps & Expectations

### Step 1: Execute the Tool

Execute the `get_issue` tool with issue number `{{TEST_ISSUE_NUMBER}}` against the target repository.

**Expectation:** The tool runs without errors and returns a single issue object with detailed information.

### Step 2: Verify Output Structure

Review the tool's output to ensure it contains comprehensive issue information.

**Expectation:** The output is an object containing the following fields: `number`, `title`, `body`, `state`, `url`, `created_at`, `updated_at`, `comments`, `labels`, and `assignees`. The `number` field should match the requested `{{TEST_ISSUE_NUMBER}}`.
