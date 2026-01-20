# Read Multiple Files in Batch

## Objective

Verify that the `read_multiple_files` tool correctly reads multiple files in a single operation.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Tools Used** | `createNewBucket`, `createFile`, `read_multiple_files`, `deleteFile` | Tools required for setup, verification, and cleanup |
| **Bucket Name** | `TC-008-read-multiple-files` | Dedicated bucket for this test case (created if missing) |

## Config

path: .alita\tool_configs\artifact-config.json
generateTestData: true

## Pre-requisites

- Alita instance is accessible and configured
- Valid API key with artifact read/write permissions
- User has permission to manage files and create buckets in the project
- Create bucket `TC-008-read-multiple-files` if missing. If it already exists, bucket creation must be treated as a non-error (idempotent).
- Ensure the bucket exists

Tool: `createNewBucket`

Input:
```json
{
  "bucket_name": "TC-008-read-multiple-files",
  "expiration_measure": "weeks",
  "expiration_value": 1
}
```

- Create files to read in batch

Tool: `createFile`

Inputs:
```json
{
  "filename": "test-document.txt",
  "filedata": "This is a test document for TC-008.\nLine 2: Testing partial reads.\nLine 3: More content here.",
  "bucket_name": "TC-008-read-multiple-files"
}
```
```json
{
  "filename": "test-readme.md",
  "filedata": "# TC-008 README\n\nThis is the README used for batch reading tests.",
  "bucket_name": "TC-008-read-multiple-files"
}
```
```json
{
  "filename": "test-data.csv",
  "filedata": "Name,Email,Role\nJohn Doe,john@example.com,Developer\nJane Doe,jane@example.com,Analyst",
  "bucket_name": "TC-008-read-multiple-files"
}
```
```json
{
  "filename": "test-data.xlsx",
  "filedata": "{\"Sheet1\": [[\"ColA\", \"ColB\"], [\"Val1\", \"Val2\"]], \"Meta\": [[\"Key\", \"Value\"], [\"Run\", \"TC-008\"]]}",
  "bucket_name": "TC-008-read-multiple-files"
}
```

## Test Steps & Expectations

### Step 1: Read Multiple Text Files

Execute the `read_multiple_files` tool to read several text files at once.

**Input:**
```json
{
  "file_paths": ["test-document.txt", "test-readme.md", "test-data.csv"],
  "bucket_name": "TC-008-read-multiple-files"
}
```

**Expectation:** The tool returns a dictionary mapping each file path to its content:
```json
{
  "test-document.txt": "This is a test document for TC-008.\nLine 2: Testing partial reads.\nLine 3: More content here.",
  "test-readme.md": "# TC-008 README\n\nThis is the README used for batch reading tests.",
  "test-data.csv": "Name,Email,Role\nJohn Doe,john@example.com,Developer\nJane Doe,jane@example.com,Analyst"
}
```

### Step 2: Read Multiple Files with Partial Read

Execute the `read_multiple_files` tool with offset and limit parameters.

**Input:**
```json
{
  "file_paths": ["test-document.txt", "test-readme.md"],
  "offset": 1,
  "limit": 2,
  "bucket_name": "TC-008-read-multiple-files"
}
```

**Expectation:** Both files return only lines 1-2 of their content.

### Step 3: Read Mix of Valid and Invalid Files

Execute the `read_multiple_files` tool with some files that don't exist.

**Input:**
```json
{
  "file_paths": ["test-document.txt", "nonexistent.txt", "test-readme.md"],
  "bucket_name": "TC-008-read-multiple-files"
}
```

**Expectation:** The tool returns content for valid files and error messages for invalid ones:
```json
{
  "test-document.txt": "This is a test document for TC-008.\nLine 2: Testing partial reads.\nLine 3: More content here.",
  "nonexistent.txt": "Error reading file: File not found",
  "test-readme.md": "# TC-008 README\n\nThis is the README used for batch reading tests."
}
```

### Step 4: Read Empty File List

Execute the `read_multiple_files` tool with an empty file list.

**Input:**
```json
{
  "file_paths": [],
  "bucket_name": "TC-008-read-multiple-files"
}
```

**Expectation:** The tool returns an empty dictionary or appropriate validation error.

### Step 5: Read Large Number of Files

Execute the `read_multiple_files` tool with many files to test batch performance.

**Input:**
```json
{
  "file_paths": ["test-document.txt", "test-readme.md", "test-data.csv", "test-data.xlsx"],
  "bucket_name": "TC-008-read-multiple-files"
}
```

**Expectation:** Text files are returned successfully. For the Excel file, the tool should either return an appropriate error or skip unsupported/binary formats. If the tool supports Excel parsing, it may return a structured representation; otherwise, an error message is acceptable.

### Cleanup — Delete Created Files (Bucket remains)

Delete the files created during setup from `TC-008-read-multiple-files`. Buckets are intentionally left in place.

Tool: `deleteFile`

Inputs:
```json
{
  "filename": "test-document.txt",
  "bucket_name": "TC-008-read-multiple-files"
}
```
```json
{
  "filename": "test-readme.md",
  "bucket_name": "TC-008-read-multiple-files"
}
```
```json
{
  "filename": "test-data.csv",
  "bucket_name": "TC-008-read-multiple-files"
}
```
```json
{
  "filename": "test-data.xlsx",
  "bucket_name": "TC-008-read-multiple-files"
}
```

**Expectation:** All specified files are deleted successfully or `None` response.
