# delete_file: Remove an obsolete file from the repository

## Priority

Critical

## Objective

Verify that the `delete_file` tool removes a specified file from the active branch and returns a deterministic confirmation message.

## Test Data Configuration

### GitHub Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Toolkit** | `github` | Toolkit under `alita_sdk/tools` |
| **Tool** | `delete_file` | Exact Python tool name |
| **Primary Input(s)** | `{{FILE_PATH}}`| Path of the file to delete; optional explicit repo name |
| **Repository** | `ProjectAlita/elitea-testing` | Target GitHub repository (owner/repo format) |
| **Branch** | `testdata-TC-052-read-multiple-files` | Branch where the file should be deleted |

## Config

path: .alita\tool_configs\git-config.json
generateTestData: true

## Pre-requisites

- Valid configuration for toolkit `github`
- Target branch is not `testdata-TC-052-read-multiple-files`
- File `{{FILE_PATH}}` exists on the active branch and can be deleted
 - Target branch for verification: `testdata-TC-052-read-multiple-files` (deletion should occur on this branch)

## Test Steps & Expectations

### Step 1: Execute the Tool

Switch `testdata-TC-052-read-multiple-files` branch and execute the `delete_file` tool using these parameters:
- `file_path`: `{{FILE_PATH}}`
- `repo_name`: `ProjectAlita/elitea-testing` (optional; omit to use default)

**Expectation:** The tool runs without errors and returns a textual success message.

### Step 2: Verify Core Output Contract

Inspect the output string.

**Expectation:** The output contains `Deleted file {{FILE_PATH}}`.

### Step 3: Confirm Absence Using read_file

After the `delete_file` tool reports success, confirm the file is actually removed from the repository branch by invoking the `read_file` tool against the verification branch.

Call `read_file` with these parameters:
- `file_path`: `{{FILE_PATH}}`
- `repo_name`: `ProjectAlita/elitea-testing`
- `branch`: `testdata-TC-052-read-multiple-files`

Expectation: `read_file` should return a clear not-found / missing-file response (for example an HTTP 404 or an explicit "file not found" message). The test MUST treat any successful file content response as a failure — the file must not exist on `testdata-TC-052-read-multiple-files` after deletion.

Notes:
- Some `read_file` implementations may return an error object or raise; the test harness should consider either a structured not-found response or an exception indicating missing file as a pass condition for this step.
- If the `read_file` call returns content, capture it and mark the test as failed and include the unexpected content in the test report.