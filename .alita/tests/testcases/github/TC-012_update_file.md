# Update File in Repository

## Objective

Verify that the `update_file` tool correctly updates an existing file's content in a GitHub repository using the OLD/NEW delimiter format, **and gracefully handles error scenarios such as ambiguous (duplicate) old content**.

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

---

## Part A: Positive Test – Successful Update

### Step 1: Read Original File Content

Use the `read_file` tool to retrieve the current content of the `test-data/generated/TC-010_sample.md` file from `tc-file-ops-2025-12-08` branch before updating and save results to `{{TEST_OLD_CONTENT}}`.

**Expectation:** The tool successfully retrieves the file content, which should not be blank.

### Step 2: Prepare Update Query

Save "{{RANDOM_STRING}} by TC-012 {{CURRENT_DATE}}" to `{{TEST_NEW_CONTENT}}`.

Build the `file_query` for:
- **File path:** `test-data/generated/TC-010_sample.md`
- **Old text:** the value of `{{TEST_OLD_CONTENT}}` (retrieved in Step 1)
- **New text:** the value of `{{TEST_NEW_CONTENT}}`

**Important:** The resulting `file_query` **MUST NOT** contain the literal placeholder text `{{TEST_OLD_CONTENT}}` or `{{TEST_NEW_CONTENT}}`; it must contain the real old and new content values.

**Expectation:** The `file_query` string is fully resolved (no placeholders) and correctly formatted with the file path, OLD delimiter markers, and NEW delimiter markers.

### Step 3: Execute the Tool

Switch to the `tc-file-ops-2025-12-08` branch and execute the `update_file` tool for the switched branch with the prepared `file_query`.

**Expectation:** The tool runs without errors and returns a success message indicating the file was updated successfully.

### Step 4: Verify Updated Content

Use the `read_file` tool to retrieve the `test-data/generated/TC-010_sample.md` file from `tc-file-ops-2025-12-08` content after the update.

**Expectation:** The file content should now contain `{{TEST_NEW_CONTENT}}` instead of `{{TEST_OLD_CONTENT}}`. The old content should be completely replaced by the new content.

---

## Part B: Negative Test – Ambiguous Old Content (Duplicate Substring)

### Objective

Verify that when the provided `OLD` content appears **more than once** in the target file, the `update_file` tool rejects the operation with an appropriate warning and leaves the file unchanged.

### Step 5: Create a File with Duplicate Content

Use the `create_file` tool to create a new file `test-data/generated/TC-012_duplicate_test.md` in the `tc-file-ops-2025-12-08` branch with content that contains a repeated substring:

```
This is a duplicate line.
Some other content here.
This is a duplicate line.
End of file.
```

Save the full file content to `{{DUPLICATE_FILE_CONTENT}}`.

**Expectation:** The file is created successfully in the repository.

### Step 6: Attempt Update with Ambiguous Old Content

Build the `file_query` for:
- **File path:** `test-data/generated/TC-012_duplicate_test.md`
- **Old text:** `This is a duplicate line.`
- **New text:** `This is the replaced line.`

Execute the `update_file` tool with this `file_query`.

**Expectation:** The tool returns an **error or warning message** indicating that the old content is ambiguous (appears more than once) and the update cannot be performed. The message should clearly state that multiple matches were found.

### Step 7: Verify File Remains Unchanged

Use the `read_file` tool to retrieve the content of `test-data/generated/TC-012_duplicate_test.md` from `tc-file-ops-2025-12-08` branch.

**Expectation:** The file content should be **identical** to `{{DUPLICATE_FILE_CONTENT}}` — no changes should have been applied. Both occurrences of "This is a duplicate line." should still be present.

### Step 8: Cleanup

Delete the test file `test-data/generated/TC-012_duplicate_test.md` from the `tc-file-ops-2025-12-08` branch using the `delete_file` tool.

**Expectation:** The file is deleted successfully.
