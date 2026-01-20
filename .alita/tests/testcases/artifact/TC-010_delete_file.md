# Delete Files and Cleanup

## Objective

Verify that the `deleteFile` tool correctly removes files from artifact buckets.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Tool** | `deleteFile` | Artifact tool to execute for file deletion |
| **Bucket Name** | `test-artifacts` | Target bucket for cleanup |
| **Primary Input(s)** | `{{TC_010_MD_FILENAME}}={{RANDOM_STRING}}.md, {{TC_010_TXT_FILENAME}}={{RANDOM_STRING}}.txt` | Required and optional inputs derived from args_schema |

## Config

path: .alita\tool_configs\artifact-config.json
generateTestData: true

## Pre-requisites

- Alita instance is accessible and configured
- Valid API key with artifact delete permissions
- Create bucket `tc-010-delete-file` if missing. If it already exists, bucket creation must be treated as a non-error (idempotent).
- Ensure the bucket exists

Tool: `createNewBucket`

Input:
```json
{
  "bucket_name": "TC-010-delete-file",
  "expiration_measure": "weeks",
  "expiration_value": 1
}
```

- Create files used for partial reads

Tool: `createFile`

Inputs:
```json
{
  "filename": "{{TC_010_TXT_FILENAME}}",
  "filedata": "This is a test document for TC-010.\nLine 2: Testing partial reads.\nLine 3: More content here.\nLine 4: Final line.",
  "bucket_name": "tc-010-delete-file"
}
```
```json
{
  "filename": "{{TC_010_TXT_FILENAME}}",
  "filedata": "This is a test document.\nLine 2: Testing partial reads.\nLine 3: More content here.\nLine 4: Final line.",
}
```

## Test Steps & Expectations

### Step 1: Delete a Single File

Execute the `deleteFile` tool to remove one test file.

**Input:**
```json
{
  "filename": "{{TC_010_TXT_FILENAME}}",
  "bucket_name": "tc-010-delete-file"
}
```

**Expectation:** The tool confirms successful deletion.

### Step 2: Verify File Deletion

List files to confirm the file was removed.

**Input:**
```json
{
  "bucket_name": "tc-010-delete-file"
}
```

**Expectation:** The file list no longer includes `{{TC_010_TXT_FILENAME}}`.

### Step 3: Attempt to Delete Non-Existent File

Execute the `deleteFile` tool on an already-deleted file.

**Input:**
```json
{
  "filename": "does_not_exist.txt",
  "bucket_name": "tc-010-delete-file"
}
```
**Expectation:** The tool returns an appropriate error message indicating the file doesn't exist.

### Step 4: Delete File from Default Bucket

Execute the `deleteFile` tool without specifying bucket_name.

**Input:**

```json
{
  "filename": "{{TC_010_TXT_FILENAME}}"
}
```

**Expectation:** The tool deletes the file from the default configured bucket.

### Step 5: Verify File Deletion

List files to confirm the file was removed.

**Input:**
```json
{
  "bucket_name": "tc-010-delete-file"
}
```

**Expectation:** The file list no longer includes `{{TC_010_TXT_FILENAME}}`.