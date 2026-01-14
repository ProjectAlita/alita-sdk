# Update File in Repository

## Objective

Verify that the `update_file` tool correctly updates an existing file's content in a GitHub repository using the OLD/NEW delimiter format.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Repository** | `ProjectAlita/elitea-testing` | Target GitHub repository (owner/repo format) |
| **Access Token** | `GIT_TOOL_ACCESS_TOKEN` | GitHub personal access token for authentication |
| **Base URL** | `https://api.github.com` | GitHub API endpoint |
| **Tool** | `update_file` | GitHub tool to execute for updating file content |
| **File Path** | `TEST_FILE_PATH` | The path of the file to update |
| **Old Content** | `TEST_OLD_CONTENT` | The old content to be replaced |
| **New Content** | `TEST_NEW_CONTENT` | The new content to replace with |
| **Active Branch** | `TEST_BRANCH` | The branch where the file will be updated (not main/master) |

## Pre-requisites

- The target repository exists and is accessible
- Valid GitHub access token with write permissions for the target repository
- The testing environment has network access to GitHub API
- The file at `TEST_FILE_PATH` exists in the target branch
- The active branch is set to a non-protected branch (not main/master)
- The file contains the old content that needs to be replaced

## Config

path: .alita\tool_configs\git-config.json
generateTestData: false

## Test Steps & Expectations

### Step 1: Read Original File Content

Use the `read_file` tool to retrieve the current content of the `test-data/generated/TC-010_sample.md` file from `tc-file-ops-2025-12-08` branch before updating and save results to `{{TEST_OLD_CONTENT}}`.

**Expectation:** The tool successfully retrieves the file content, which should not be blank.

### Step 2: Prepare Update Query

Save "{{RANDOM_STRING}} by TC-012 {{CURRENT_DATE}}" to {{TEST_NEW_CONTENT}} before preparing the file_query.

Prepare the file_query parameter in the correct format:
```
test-data/generated/TC-010_sample.md
OLD <<<<
{{TEST_OLD_CONTENT}}
>>>> OLD
NEW <<<<
{{TEST_NEW_CONTENT}}
>>>> NEW
```

**Expectation:** The query string is properly formatted with the file path, OLD delimiter markers, and NEW delimiter markers.

### Step 3: Execute the Tool

Switch to the `tc-file-ops-2025-12-08` branch and execute the `update_file` tool for the switched branch with the prepared file_query.

**Expectation:** The tool runs without errors and returns a success message indicating the file was updated successfully.

### Step 4: Verify Updated Content

Use the `read_file` tool to retrieve the `test-data/generated/TC-010_sample.md` file from `tc-file-ops-2025-12-08` content after the update.

**Expectation:** The file content should now contain `{{TEST_NEW_CONTENT}}` instead of `{{TEST_OLD_CONTENT}}`. The old content should be completely replaced by the new content.
