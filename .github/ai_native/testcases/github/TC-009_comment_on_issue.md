# Comment on Issue

## Objective

Verify that the `comment_on_issue` tool correctly adds a comment to an existing issue or pull request in a GitHub repository.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Repository** | `VladVariushkin/agent` | Target GitHub repository (owner/repo format) |
| **Access Token** | `GIT_TOOL_ACCESS_TOKEN` | GitHub personal access token for authentication |
| **Base URL** | `https://api.github.com` | GitHub API endpoint |
| **Tool** | `comment_on_issue` | GitHub tool to execute for adding a comment |
| **Issue Number** | `TEST_ISSUE_NUMBER` | The issue number to comment on |
| **Comment Text** | `TEST_COMMENT_TEXT` | The text content of the comment to add |

## Pre-requisites

- The target repository exists and is accessible
- Valid GitHub access token with write permissions for the target repository
- The testing environment has network access to GitHub API
- Issue with number `TEST_ISSUE_NUMBER` exists in the repository
- The access token has permission to comment on issues

## Config

path: .alita\tool_configs\git-config.json

## Test Steps & Expectations

### Step 1: Execute the Tool

Execute the `comment_on_issue` tool with issue number `{{TEST_ISSUE_NUMBER}}` and comment text `{{TEST_COMMENT_TEXT}}`.

**Expectation:** The tool runs without errors and returns a success message containing the comment URL.

### Step 2: Verify Success Message

Review the tool's output to ensure it confirms comment creation.

**Expectation:** The output should contain a success message like "Comment added successfully!" and include a URL to the newly created comment. The URL should follow the pattern `https://github.com/<owner>/<repo>/issues/<number>#issuecomment-<comment_id>`.

### Step 3: Verify Comment Persistence

Retrieve the issue again using `get_issue` tool to verify the comment was added.

**Expectation:** The `comments` count in the issue should have increased by 1 compared to before the comment was added. The comment should be visible when viewing the issue on GitHub.