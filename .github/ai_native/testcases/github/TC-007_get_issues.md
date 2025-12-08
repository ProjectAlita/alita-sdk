# Get Issues List

## Objective

Verify that the `get_issues` tool correctly retrieves a list of issues from a GitHub repository with proper filtering by state (open, closed, or all).

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Repository** | `ProjectAlita/elitea-testing` | Target GitHub repository (owner/repo format) |
| **Access Token** | `GIT_TOOL_ACCESS_TOKEN` | GitHub personal access token for authentication |
| **Base URL** | `https://api.github.com` | GitHub API endpoint |
| **Tool** | `get_issues` | GitHub tool to execute for retrieving issues list |
| **State** | `open` | Filter by issue state (open, closed, or all) |

## Pre-requisites

- The target repository exists and is accessible
- Valid GitHub access token with appropriate permissions for the target repository
- The testing environment has network access to GitHub API
- Repository has at least one issue created

## Config

path: .alita\tool_configs\git-config.json
generateTestData: false

## Test Steps & Expectations

### Step 1: Execute the Tool with Default State

Execute the `get_issues` tool with default parameters (state="open") against the target repository.

**Expectation:** The tool runs without errors and returns a list of issue objects.

### Step 2: Verify Output Structure

Review the tool's output to ensure it contains proper issue information.

**Expectation:** The output is a list of issue objects. Each issue object should contain the following fields: `number`, `title`, `state`, `created_at`, `updated_at`, `url`, `labels`, and `assignees`. All `state` fields should show "open" when filtered by open state.