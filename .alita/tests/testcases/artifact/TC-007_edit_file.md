# Edit File with OLD/NEW Markers

## Objective

Verify that the `edit_file` tool correctly edits text files using OLD/NEW markers for precise replacements.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Base URL** | `${ALITA_BASE_URL}` | Alita instance base URL |
| **Project ID** | `${ALITA_PROJECT_ID}` | Project ID for artifact storage |
| **API Key** | `${ALITA_API_KEY}` | Authentication token |
| **Tool** | `edit_file` | Artifact tool to execute for editing files |
| **Bucket Name** | `test-artifacts` | Target bucket containing files to edit |

## Config

path: .alita\tool_configs\artifact-config.json
generateTestData: false

## Pre-requisites

- Alita instance is accessible and configured
- Valid API key with artifact write permissions
- Bucket `test-artifacts` exists with editable text files
- Files created in TC-002 are available for editing

## Test Steps & Expectations

### Step 1: Edit Single Line

Execute the `edit_file` tool to replace a single line in the test document.

**Input:**
```json
{
  "file_path": "test-document.txt",
  "file_query": "OLD <<<<\nLine 2: Testing partial reads.\n>>>> OLD\nNEW <<<<\nLine 2: Testing partial reads and edits.\n>>>> NEW",
  "bucket_name": "test-artifacts"
}
```

**Expectation:** The tool successfully updates line 2, changing "partial reads" to "partial reads and edits".

### Step 2: Verify Edit

Read the file to confirm the edit was applied.

**Input:**
```json
{
  "filename": "test-document.txt",
  "bucket_name": "test-artifacts"
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
  "bucket_name": "test-artifacts"
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
  "bucket_name": "test-artifacts"
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
  "bucket_name": "test-artifacts"
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
  "bucket_name": "test-artifacts"
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
  "bucket_name": "test-artifacts"
}
```

**Expectation:** The tool returns a message indicating no changes were made because the old content was not found, suggesting to use read_file to verify current content.
