# Edit File with OLD/NEW Markers

## Priority

Critical

## Objective

Verify that the `edit_file` tool correctly edits text files using OLD/NEW markers for precise replacements.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Tools Used** | `createNewBucket`, `createFile`, `edit_file`, `readFile`, `deleteFile` | Tools required for setup, verification, and cleanup |
| **Bucket Name** | `TC-007-edit-file` | Dedicated bucket for this test case (created if missing) |

## Config

path: .alita\tool_configs\artifact-config.json
generateTestData: true

## Pre-requisites

 - Alita instance is accessible and configured
 - Valid API key with artifact read/write permissions
 - User has permission to manage files and create buckets in the project
 - Create bucket `TC-007-edit-file` if missing. If it already exists, bucket creation must be treated as a non-error (idempotent).
- Ensure the bucket exists

Tool: `createNewBucket`

Input:
```json
{
  "bucket_name": "TC-007-edit-file",
  "expiration_measure": "weeks",
  "expiration_value": 1
}
```

- Create files to edit and verify

Tool: `createFile`

Inputs:
```json
{
  "filename": "test-document.txt",
  "filedata": "This is a test document for TC-007.\nLine 2: Testing partial reads.\nLine 3: More content here.\nLine 4: Final line.",
  "bucket_name": "TC-007-edit-file"
}
```
```json
{
  "filename": "test-readme.md",
  "filedata": "# TC-007 README\n\n## Section 1\nContent for section 1.",
  "bucket_name": "TC-007-edit-file"
}
```
```json
{
  "filename": "test-data.csv",
  "filedata": "Name,Email,Role\nJohn Doe,john@example.com,Developer\nJane Doe,jane@example.com,Analyst",
  "bucket_name": "TC-007-edit-file"
}
```
```json
{
  "filename": "test-data.xlsx",
  "filedata": "{\"Sheet1\": [[\"ColA\", \"ColB\"], [\"Val1\", \"Val2\"]], \"Meta\": [[\"Key\", \"Value\"], [\"Run\", \"TC-007\"]]}",
  "bucket_name": "TC-007-edit-file"
}
```

## Test Steps & Expectations

### Step 1: Edit Single Line

Execute the `edit_file` tool to replace a single line in the test document.

**Input:**
```json
{
  "file_path": "test-document.txt",
  "file_query": "OLD <<<<\nLine 2: Testing partial reads.\n>>>> OLD\nNEW <<<<\nLine 2: Testing partial reads and edits.\n>>>> NEW",
  "bucket_name": "TC-007-edit-file"
}
```

**Expectation:** The tool successfully updates line 2, changing "partial reads" to "partial reads and edits".

### Step 2: Verify Edit

Read the file to confirm the edit was applied.

**Input:**
```json
{
  "filename": "test-document.txt",
  "bucket_name": "TC-007-edit-file"
}
```

**Expectation:** The file content shows the updated line 2.

### Step 3: Edit Markdown Header

Execute the `edit_file` tool to modify markdown content.

**Input:**
```json
{
  "file_path": "test-readme.md",
  "file_query": "OLD <<<<\n## Section 1\nContent for section 1.\n>>>> OLD\nNEW <<<<\n## Section 1 - Updated\nUpdated content for section 1.\nAdditional line added.\n>>>> NEW",
  "bucket_name": "TC-007-edit-file"
}
```

**Expectation:** The markdown section is updated with new header and content.

### Step 4: Multiple Edits in One Call

Execute the `edit_file` tool with multiple OLD/NEW pairs.

**Input:**
```json
{
  "file_path": "test-document.txt",
  "file_query": "OLD <<<<\nLine 3: More content here.\n>>>> OLD\nNEW <<<<\nLine 3: Modified content.\n>>>> NEW\nOLD <<<<\nLine 4: Final line.\n>>>> OLD\nNEW <<<<\nLine 4: Updated final line.\n>>>> NEW",
  "bucket_name": "TC-007-edit-file"
}
```

**Expectation:** Both replacements are applied successfully in a single operation.

### Step 5: Edit CSV Data

Execute the `edit_file` tool to modify CSV content.

**Input:**
```json
{
  "file_path": "test-data.csv",
  "file_query": "OLD <<<<\nJohn Doe,john@example.com,Developer\n>>>> OLD\nNEW <<<<\nJohn Doe,john.doe@example.com,Senior Developer\n>>>> NEW",
  "bucket_name": "TC-007-edit-file"
}
```

**Expectation:** The CSV row is updated with the new email and role.

### Step 6: Attempt Edit on Binary File

Execute the `edit_file` tool on the Excel file (should be rejected).

**Input:**
```json
{
  "file_path": "test-data.xlsx",
  "file_query": "OLD <<<<\nsome content\n>>>> OLD\nNEW <<<<\nnew content\n>>>> NEW",
  "bucket_name": "TC-007-edit-file"
}
```

**Expectation:** The tool returns an error indicating that binary/Excel files cannot be edited with this tool. Only text files (.txt, .md, .csv, .json, etc.) are supported.

### Step 7: Edit with Non-Matching OLD Content

Execute the `edit_file` tool with OLD content that doesn't exist.

**Input:**
```json
{
  "file_path": "test-document.txt",
  "file_query": "OLD <<<<\nThis line does not exist\n>>>> OLD\nNEW <<<<\nNew content\n>>>> NEW",
  "bucket_name": "TC-007-edit-file"
}
```

**Expectation:** The tool returns a message indicating no changes were made because the old content was not found, suggesting to use read_file to verify current content.

### Cleanup — Delete Created Files (Bucket remains)

Delete the files created during setup from `TC-007-edit-file`. Buckets are intentionally left in place.

Tool: `deleteFile`

Inputs:
```json
{
  "filename": "test-document.txt",
  "bucket_name": "TC-007-edit-file"
}
```
```json
{
  "filename": "test-readme.md",
  "bucket_name": "TC-007-edit-file"
}
```
```json
{
  "filename": "test-data.csv",
  "bucket_name": "TC-007-edit-file"
}
```
```json
{
  "filename": "test-data.xlsx",
  "bucket_name": "TC-007-edit-file"
}
```

**Expectation:** All specified files are deleted successfully or `None` response.
