# Append and Overwrite Data

## Objective

Verify that the `appendData` and `overwriteData` tools correctly modify file contents in artifact buckets.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Tools** | `appendData`, `overwriteData`, `readFile` | Artifact tools for data modification |
| **Bucket Name** | `TC-009-append-overwrite` | Target bucket for operations |
| **Primary Input(s)** | `TC_009_MD_FILENAME={{RANDOM_STRING}}.md, TC_009_TXT_FILENAME={{RANDOM_STRING}}.txt, TC_009_NON_EXISTENT_FILENAME={{RANDOM_STRING}}.txt, TC_009_CSV_FILENAME={{RANDOM_STRING}}.csv,` | Required and optional inputs derived from args_schema |

## Config

path: .alita\tool_configs\artifact-config.json
generateTestData: true

## Pre-requisites

- Alita instance is accessible and configured
- Valid API key with artifact write permissions
- Create bucket `tc-009-append-overwrite` if missing. If it already exists, bucket creation must be treated as a non-error (idempotent).
Tool: `createNewBucket`

Input:
```json
{
  "bucket_name": "tc-009-append-overwrite",
  "expiration_measure": "weeks",
  "expiration_value": 1
}
```

- Create files to read

Tool: `createFile`

Inputs:
```json
{
  "filename": "{{TC_009_TXT_FILENAME}}",
  "filedata": "This is a test document for TC-009.\nSecond line.",
  "bucket_name": "tc-009-append-overwrite"
}
```
```json
{
  "filename": "{{TC_009_MD_FILENAME}}",
  "filedata": "# TC-009 README\n\nThis is a markdown file used for read-file verification.",
  "bucket_name": "tc-009-append-overwrite"
}
```
```json
{
  "filename": "{{TC_009_CSV_FILENAME}}",
  "filedata": "Name,Age,City\nAlice,30,NYC\nBob,25,LA",
  "bucket_name": "tc-009-append-overwrite"
}
```

## Test Steps & Expectations

### Step 1: Append Data to Text File

Execute the `appendData` tool to add content to an existing file.

**Input:**
```json
{
  "filename": "{{TC_009_TXT_FILENAME}}",
  "filedata": "Line 5: Appended content.\nLine 6: More appended data.",
  "bucket_name": "tc-009-append-overwrite"
}
```

**Expectation:** The tool successfully appends the data and confirms with a success message.

### Step 2: Verify Append Operation

Run readFile tool to confirm data was appended.

**Input:**
```json
{
  "filename": "{{TC_009_TXT_FILENAME}}",
  "bucket_name": "tc-009-append-overwrite"
}
```

**Expectation:** The file now contains the original 2 lines plus the 2 appended lines (total 4 lines).

### Step 3: Append to CSV File

Execute the `appendData` tool to add a new row to the CSV.

**Input:**
```json
{
  "filename": "{{TC_009_CSV_FILENAME}}",
  "filedata": "Max,44,LA",
  "bucket_name": "tc-009-append-overwrite"
}
```

**Expectation:** The new row is appended to the CSV file.

### Step 4: Verify Append Operation

Run readFile tool to confirm data was appended.

**Input:**
```json
{
  "filename": "{{TC_009_CSV_FILENAME}}",
  "bucket_name": "tc-009-append-overwrite"
}
```

**Expectation:** The file now contains the original 3 lines plus the 1 appended lines (total 4 lines).

### Step 5: Overwrite File Content

Execute the `overwriteData` tool to replace entire file content.

**Input:**
```json
{
  "filename": "{{TC_009_TXT_FILENAME}}",
  "filedata": "Completely new content.\nAll previous data replaced.\nThis is the new file.",
  "bucket_name": "tc-009-append-overwrite"
}
```

**Expectation:** The tool successfully overwrites the file and confirms with a success message.

### Step 5: Verify Overwrite Operation

Read the file to confirm it was completely replaced.

**Input:**
```json
{
  "filename": "{{TC_009_TXT_FILENAME}}",
  "bucket_name": "tc-009-append-overwrite"
}
```

**Expectation:** The file contains only the new content (3 lines), all previous content is gone.

### Step 6: Overwrite Markdown File

Execute the `overwriteData` tool to replace markdown content.

**Input:**
```json
{
  "filename": "{{TC_009_MD_FILENAME}}",
  "filedata": "# Updated README\n\nThis file has been completely rewritten.\n\n## New Structure\n- Point 1\n- Point 2",
  "bucket_name": "tc-009-append-overwrite"
}
```

**Expectation:** The markdown file is completely replaced with new structure.

## Step 7: Verify Overwrite Operation

Read the file to confirm it was completely replaced.

**Input:**
```json
{
  "filename": "{{TC_009_MD_FILENAME}}",
  "bucket_name": "tc-009-append-overwrite"
}
```

**Expectation:** The file contains only the new content (5 lines), all previous content is gone.

### Step 8: Append to Non-Existent File

Execute the `appendData` tool on a file that doesn't exist.

**Input:**
```json
{
  "filename": "{{TC_009_NON_EXISTENT_FILENAME}}",
  "filedata": "Creating new file via append",
  "bucket_name": "tc-009-append-overwrite"
}
```

**Expectation:** The tool creates the file with the provided content (append on empty/new file).

### Step 9: Verify Overwrite Operation

Read the file to confirm it was completely replaced.

**Input:**
```json
{
  "filename": "{{TC_009_NON_EXISTENT_FILENAME}}",
  "bucket_name": "tc-009-append-overwrite"
}
```

**Expectation:** The file contains one line `Creating new file via append`.


### Step 10: Overwrite with Empty Content

Execute the `overwriteData` tool with empty string.

**Input:**
```json
{
  "filename": "{{TC_009_TXT_FILENAME}}",
  "filedata": "",
  "bucket_name": "tc-009-append-overwrite"
}
```

**Expectation:** The file is replaced with an empty file (0 bytes or minimal content).

### Step 11: Cleanup — Delete Created Files (Bucket remains)

Delete the files created during setup from `tc-009-append-overwrite`. Buckets are intentionally left in place.

Tool: `deleteFile`

Inputs:
```json
{
  "filename": "{{TC_009_TXT_FILENAME}}",
  "bucket_name": "tc-009-append-overwrite"
}
```
```json
{
  "filename": "{{TC_009_MD_FILENAME}}",
  "bucket_name": "tc-009-append-overwrite"
}
```
```json
{
  "filename": "{{TC_009_NON_EXISTENT_FILENAME}}",
  "bucket_name": "tc-009-append-overwrite"
}
```
```json
{
  "filename": "{{TC_009_CSV_FILENAME}}",
  "bucket_name": "tc-009-append-overwrite"
}
```
**Expectation:** Verify success messaga that files `{{TC_009_MD_FILENAME}}`, `{{TC_009_TXT_FILENAME}}`, `{{TC_009_NON_EXISTENT_FILENAME}}`, and `{{TC_009_CSV_FILENAME}}` were deleted.

