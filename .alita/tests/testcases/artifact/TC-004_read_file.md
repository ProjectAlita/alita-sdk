# Read File from Artifact

## Priority

Critical

## Objective

Verify that the `readFile` tool correctly retrieves file content from an artifact bucket with various options.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Tools Used** | `createNewBucket`, `createFile`, `readFile`, `deleteFile` | Tools required for setup, verification, and cleanup |
| **Bucket Name** | `tc-004-read-file` | Dedicated bucket for this test case (created if missing) |
| **Primary Input(s)** | `TC_004_MD_FILENAME={{RANDOM_STRING}}.md, TC_004_TXT_FILENAME={{RANDOM_STRING}}.txt, TC_004_XLSX_FILENAME={{RANDOM_STRING}}.xlsx, TC_004_CSV_FILENAME={{RANDOM_STRING}}.csv,` | Required and optional inputs derived from args_schema |

## Config

path: .alita\tool_configs\artifact-config.json
generateTestData: true

## Pre-requisites

- Alita instance is accessible and configured
- Valid API key with artifact read/write permissions
- User has permission to manage files and create buckets in the project
- Create bucket `TC-004-read-file` if missing. If it already exists, bucket creation must be treated as a non-error (idempotent).
Tool: `createNewBucket`

Input:
```json
{
  "bucket_name": "tc-004-read-file",
  "expiration_measure": "weeks",
  "expiration_value": 1
}
```

- Create files to read

Tool: `createFile`

Inputs:
```json
{
  "filename": "{{TC_004_TXT_FILENAME}}",
  "filedata": "This is a test document for TC-004.\nSecond line.",
  "bucket_name": "tc-004-read-file"
}
```
```json
{
  "filename": "{{TC_004_MD_FILENAME}}",
  "filedata": "# TC-004 README\n\nThis is a markdown file used for read-file verification.",
  "bucket_name": "tc-004-read-file"
}
```
```json
{
  "filename": "{{TC_004_XLSX_FILENAME}}",
  "filedata": "{\"Sheet1\": [[\"Name\", \"Age\", \"City\"], [\"Alice\", 30, \"NYC\"], [\"Bob\", 25, \"LA\"]], \"Sheet2\": [[\"Key\", \"Value\"], [\"Run\", \"TC-004\"]]}",
  "bucket_name": "tc-004-read-file"
}
```
```json
{
  "filename": "{{TC_004_CSV_FILENAME}}",
  "filedata": "Name,Age,City\nAlice,30,NYC\nBob,25,LA",
  "bucket_name": "tc-004-read-file"
}
```

## Test Steps & Expectations

### Step 1: Read a Text File

Execute the `readFile` tool to read a simple text file.

**Input:**
```json
{
  "filename": "{{TC_004_TXT_FILENAME}}",
  "bucket_name": "tc-004-read-file"
}
```

**Expectation:** The tool returns the complete file content as a string matching the original content.

### Step 2: Read a Markdown File

Execute the `readFile` tool to read the markdown file.

**Input:**
```json
{
  "filename": "{{TC_004_MD_FILENAME}}",
  "bucket_name": "tc-004-read-file"
}
```

**Expectation:** The markdown content is returned correctly with all formatting preserved.

### Step 3: Read Excel File - All Sheets

Execute the `readFile` tool to read the Excel file with all sheets.

**Input:**
```json
{
  "filename": "{{TC_004_XLSX_FILENAME}}",
  "bucket_name": "tc-004-read-file",
  "excel_by_sheets": true
}
```

**Expectation:** The tool returns both sheets present

### Step 4: Read Excel File - Specific Sheet

Execute the `readFile` tool to read only a specific sheet from the Excel file.

**Input:**
```json
{
  "filename": "{{TC_004_XLSX_FILENAME}}",
  "bucket_name": "tc-004-read-file",
  "sheet_name": "Sheet1"
}
```

**Expectation:** The tool returns only the data from Sheet1 (Name, Age, City table).

### Step 5: Read CSV File

Execute the `readFile` tool to read the CSV file.

**Input:**
```json
{
  "filename": "{{TC_004_CSV_FILENAME}}",
  "bucket_name": "tc-004-read-file"
}
```

**Expectation:** The CSV content is returned as plain text with proper line breaks.

### Step 6: Read Non-Existent File

Execute the `readFile` tool to read a file that doesn't exist.

**Input:**
```json
{
  "filename": "non-existent-file.txt",
  "bucket_name": "tc-004-read-file"
}
```

**Expectation:** The tool returns an appropriate error message indicating the file was not found.

### Step 7: Cleanup — Delete Created Files (Bucket remains)

Delete the files created during setup from `tc-004-read-file`. Buckets are intentionally left in place.

Tool: `deleteFile`

Inputs:
```json
{
  "filename": "{{TC_004_TXT_FILENAME}}",
  "bucket_name": "tc-004-read-file"
}
```
```json
{
  "filename": "{{TC_004_MD_FILENAME}}",
  "bucket_name": "tc-004-read-file"
}
```
```json
{
  "filename": "{{TC_004_XLSX_FILENAME}}",
  "bucket_name": "tc-004-read-file"
}
```
```json
{
  "filename": "{{TC_004_CSV_FILENAME}}",
  "bucket_name": "tc-004-read-file"
}
```

**Expectation:** Verify success messages for files `{{TC_004_MD_FILENAME}}`, `{{TC_004_TXT_FILENAME}}`, `{{TC_004_XLSX_FILENAME}}`, and `{{TC_004_CSV_FILENAME}}` deletion.
