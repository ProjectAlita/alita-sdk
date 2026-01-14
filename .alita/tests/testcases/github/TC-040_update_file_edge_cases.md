# Update File Edge Cases

## Objective

Verify that the `update_file` tool gracefully handles error scenarios such as ambiguous content, empty blocks, whitespace-only content, content not found, and multiple candidate regions. Also verify positive edge cases like tolerant whitespace matching, replacing content with empty string, and full file replacement.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Repository** | `ProjectAlita/elitea-testing` | Target GitHub repository (owner/repo format) |
| **Access Token** | `GIT_TOOL_ACCESS_TOKEN` | GitHub personal access token for authentication |
| **Base URL** | `https://api.github.com` | GitHub API endpoint |
| **Tool** | `update_file` | GitHub tool to execute for updating file content |

]=| **Active Branch** | `TC_040_BRANCH` | The branch where tests will be executed (not main/master) |

## Pre-requisites

- The target repository exists and is accessible
- Valid GitHub access token with write permissions for the target repository
- The testing environment has network access to GitHub API
- The active branch is set to a non-protected branch (not main/master)

## Config

path: .alita\tool_configs\git-config.json
generateTestData: false

---

## Setup: Create All Test Files

### Objective

Create all necessary test files at the beginning with optimized content that can be reused across multiple test scenarios. This minimizes tool calls and improves test stability.

### Step 1: Generate Unique File Names

Generate unique file names using current date and random string:
- Save `tc-040-update-file-{{CURRENT_DATE}}` to `{{TC_040_BRANCH}}`
- Save `TC-040_{{CURRENT_DATE}}_{{RANDOM_STRING}}_main.md` to `{{TC_040_FILE_MAIN}}`
- Save `TC-040_{{CURRENT_DATE}}_{{RANDOM_STRING}}_whitespace.md` to `{{TC_040_FILE_WHITESPACE}}`
- Save `TC-040_{{CURRENT_DATE}}_{{RANDOM_STRING}}_replace.md` to `{{TC_040_FILE_REPLACE}}`

**Expectation:** A unique branch name and three unique file names are generated with current date and random components.

### Step 2: Create Main Test File
Use the `create_file` tool to create a new file `test-data/generated/{{TC_040_FILE_MAIN}}` in the `{{TC_040_BRANCH}}` branch with the following content designed to support multiple test scenarios:

```
This is a duplicate line.
Some other content here.
This is a duplicate line.
---SECTION-SEPARATOR---
Line one of the file.
Line two of the file.
Line three of the file.
---SECTION-SEPARATOR---
Some content in the file.
More content here.
---SECTION-SEPARATOR---
Header line stays.
This line will be deleted.
Footer line stays.
---SECTION-SEPARATOR---
Greeting   Message   Here
Some other content.
Greeting    Message    Here
More content here.
End of main test file.
```
Save the full file content to `{{TC_040_MAIN_FILE_CONTENT}}`.

**Expectation:** The main test file is created successfully in the repository containing content for:
- Part A: Duplicate line tests (lines 1-3)
- Part B: Not found tests (lines 5-7)
- Part C: Empty OLD block tests (lines 9-10)
- Part G: Multiple candidate tests (lines 16-19)
- Part G: Multiple candidate tests (lines 16-19) - Note: Both lines have extra spaces but different spacing patterns, so neither is an exact match for normalized "Greeting Message Here"

### Step 3: Create Whitespace Test File
Use the `create_file` tool to create a new file `test-data/generated/{{TC_040_FILE_WHITESPACE}}` in the `{{TC_040_BRANCH}}` branch with whitespace variations:

```
   First line with leading spaces.
Second line   with   extra   internal   spaces.
Third line with trailing spaces.   

Fourth line after empty line.
```
Save the full file content to `{{TC_040_WHITESPACE_FILE_CONTENT}}`.

**Expectation:** The whitespace test file is created successfully for Part D tests.

### Step 4: Create Full Replace Test File
Use the `create_file` tool to create a new file `test-data/generated/{{TC_040_FILE_REPLACE}}` in the `{{TC_040_BRANCH}}` branch:

```
Original line 1.
Original line 2.
Original line 3.
```
Save the full file content to `{{TC_040_FULL_REPLACE_ORIGINAL}}`.

**Expectation:** The full replace test file is created successfully for Part F tests.

---

## Part A: Negative Test – Ambiguous Old Content (Duplicate Substring)

### Objective

Verify that when the provided `OLD` content appears **more than once** in the target file, the `update_file` tool rejects the operation with an appropriate warning and leaves the file unchanged.

### Step 5: Attempt Update with Ambiguous Old Content

- **File path:** `test-data/generated/{{TC_040_FILE_MAIN}}`
- **Old text:** `This is a duplicate line.`
- **New text:** `This is the replaced line.`

Execute the `update_file` tool with this `file_query`.

**Expectation:** The tool returns a **warning message** indicating that the old content is ambiguous (appears more than once) and the update cannot be performed. The message should contain text like "appears X times" or "multiple matches".

### Step 6: Verify File Remains Unchanged
Use the `read_file` tool to retrieve the content of `test-data/generated/{{TC_040_FILE_MAIN}}` from `{{TC_040_BRANCH}}` branch.
**Expectation:** The file content should be **identical** to `{{TC_040_MAIN_FILE_CONTENT}}` — no changes should have been applied. Both occurrences of "This is a duplicate line." should still be present.

---

## Part B: Negative Test – OLD Content Not Found

### Objective

Verify that when the provided `OLD` content does not exist in the target file, the `update_file` tool returns an appropriate warning and leaves the file unchanged.

### Step 7: Attempt Update with Non-Existent Old Content

- **File path:** `test-data/generated/{{TC_040_FILE_MAIN}}`
- **Old text:** `This text absolutely does not exist anywhere in the file XYZ123.`
- **New text:** `Replacement text.`

Execute the `update_file` tool with this `file_query`.

**Expectation:** The tool returns a **warning message** indicating that the OLD block was not found in the file. The message should contain text like "not found".

### Step 8: Verify File Remains Unchanged
Use the `read_file` tool to retrieve the content of `test-data/generated/{{TC_040_FILE_MAIN}}` from `{{TC_040_BRANCH}}` branch.
**Expectation:** The file content should be **identical** to `{{TC_040_MAIN_FILE_CONTENT}}` — no changes should have been applied.

---

## Part C: Negative Test – Empty OLD Block

### Objective

Verify that when the provided `OLD` block is empty or contains only whitespace, the `update_file` tool returns an appropriate warning and leaves the file unchanged.

### Step 9: Attempt Update with Empty OLD Block

- **File path:** `test-data/generated/{{TC_040_FILE_MAIN}}`
- **Old text:** `` (empty string - nothing between OLD markers)
- **New text:** `This should not be inserted.`

Execute the `update_file` tool with this `file_query`.
**Expectation:** The tool returns a **warning message** indicating that the OLD block is empty or whitespace-only. The message should contain text like "empty" or "whitespace-only".
**Expectation:** The tool returns a **warning message** indicating that the OLD block is empty or whitespace-only. The message should contain text like "empty" or "whitespace-only" or "redundant" or "self-cancelling".

### Step 10: Attempt Update with Whitespace-Only OLD Block

- **File path:** `test-data/generated/{{TC_040_FILE_MAIN}}`
- **Old text:** `   ` (only spaces/whitespace between OLD markers)
- **New text:** `This should not be inserted.`

Execute the `update_file` tool with this `file_query`.
**Expectation:** The tool returns a **warning message** indicating that the OLD block is empty or contains only whitespace. The message should contain text like "empty" or "whitespace-only".
**Expectation:** The tool returns a **warning message** indicating that the OLD block is empty or contains only whitespace. The message should contain text like "empty" or "whitespace-only" or "redundant" or "self-cancelling".

### Step 11: Verify File Remains Unchanged
Use the `read_file` tool to retrieve the content of `test-data/generated/{{TC_040_FILE_MAIN}}` from `{{TC_040_BRANCH}}` branch.
**Expectation:** The file content should be **identical** to `{{TC_040_MAIN_FILE_CONTENT}}` — no changes should have been applied.

---

## Part D: Positive Test – Tolerant Matching with Extra Whitespace

### Objective

Verify that the `update_file` tool can handle content with extra spaces and newlines at the start, end, or middle by using tolerant (normalized) matching.

### Step 12: Update Content Using Normalized Match

- **File path:** `test-data/generated/{{TC_040_FILE_WHITESPACE}}`
- **Old text:** `Second line with extra internal spaces.` (normalized version without multiple spaces)
- **New text:** `Second line updated successfully.`

Execute the `update_file` tool with this `file_query`.

**Expectation:** The tool uses tolerant matching to find the content despite whitespace differences and successfully replaces it. A success message is returned.

### Step 13: Verify Updated Content
Use the `read_file` tool to retrieve the content of `test-data/generated/{{TC_040_FILE_WHITESPACE}}` from `{{TC_040_BRANCH}}` branch.

**Expectation:** The file content should contain `Second line updated successfully.` instead of the original line with extra spaces.

---

## Part E: Positive Test – Replace Content with Empty String (Delete Content)

### Objective

Verify that the `update_file` tool can replace existing content with an empty string, effectively deleting that portion of the file.

### Step 14: Replace Content with Empty String

- **File path:** `test-data/generated/{{TC_040_FILE_MAIN}}`
- **Old text:** `This line will be deleted.`
- **New text:** `` (empty string - nothing between NEW markers)

Execute the `update_file` tool with this `file_query`.

**Expectation:** The tool runs without errors and returns a success message indicating the file was updated successfully.

### Step 15: Verify Content Was Deleted
Use the `read_file` tool to retrieve the content of `test-data/generated/{{TC_040_FILE_MAIN}}` from `{{TC_040_BRANCH}}` branch.

**Expectation:** The file content should no longer contain "This line will be deleted." The line should have been removed from the file.
Save the updated content to `{{TC_040_MAIN_FILE_CONTENT}}` for subsequent tests.

---

## Part F: Positive Test – Replace Entire File Content

### Objective

Verify that the `update_file` tool can replace the entire content of a file with new content.

### Step 16: Replace Entire File Content

- **File path:** `test-data/generated/{{TC_040_FILE_REPLACE}}`
- **Old text:** the value of `{{TC_040_FULL_REPLACE_ORIGINAL}}` (entire original content)
- **New text:** `Completely new content.\nReplaced by TC-040 {{CURRENT_DATE}}.`

Execute the `update_file` tool with this `file_query`.

**Expectation:** The tool runs without errors and returns a success message indicating the file was updated successfully.

### Step 17: Verify Full Replacement
Use the `read_file` tool to retrieve the content of `test-data/generated/{{TC_040_FILE_REPLACE}}` from `{{TC_040_BRANCH}}` branch.

**Expectation:** The file content should be completely replaced with the new content. None of the original lines ("Original line 1.", "Original line 2.", "Original line 3.") should exist.

---

## Part G: Negative Test – Multiple Candidate Regions (Tolerant Match Ambiguity)

### Objective

Verify that when the normalized OLD content matches multiple regions in the file (via tolerant matching), the tool rejects the operation to avoid ambiguity.

### Step 18: Attempt Update with Ambiguous Normalized Match

- **File path:** `test-data/generated/{{TC_040_FILE_MAIN}}`
- **Old text:** `Greeting Message Here`
- **New text:** `Goodbye Message`

Execute the `update_file` tool with this `file_query`.

**Expectation:** The tool returns a **warning message** indicating multiple candidate regions were found. The message should contain text like "multiple" or "ambiguous" or "appears X times".
Note: The main file contains both "Hello   World" (with extra spaces) and "Hello World" which both normalize to "Hello World".
Note: The main file contains both "Greeting   Message   Here" (with 3 spaces) and "Greeting    Message    Here" (with 4 spaces). Neither is an exact match for "Greeting Message Here" (single spaces), but both normalize to the same value, triggering the ambiguity check in tolerant matching.

### Step 19: Verify File Remains Unchanged
Use the `read_file` tool to retrieve the content of `test-data/generated/{{TC_040_FILE_MAIN}}` from `{{TC_040_BRANCH}}` branch.
**Expectation:** The file content should still contain both "Greeting   Message   Here" and "Greeting    Message    Here" — no changes should have been applied due to ambiguity.

---

## Cleanup: Delete All Test Files

### Step 20: Delete Main Test File
Delete the test file `test-data/generated/{{TC_040_FILE_MAIN}}` from the `{{TC_040_BRANCH}}` branch using the `delete_file` tool.

**Expectation:** The file is deleted successfully.

### Step 21: Delete Whitespace Test File
Delete the test file `test-data/generated/{{TC_040_FILE_WHITESPACE}}` from the `{{TC_040_BRANCH}}` branch using the `delete_file` tool.

**Expectation:** The file is deleted successfully.

### Step 22: Delete Full Replace Test File
Delete the test file `test-data/generated/{{TC_040_FILE_REPLACE}}` from the `{{TC_040_BRANCH}}` branch using the `delete_file` tool.

**Expectation:** The file is deleted successfully.
