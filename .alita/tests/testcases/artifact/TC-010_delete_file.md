# Delete Files and Cleanup

## Objective

Verify that the `deleteFile` tool correctly removes files from artifact buckets.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Base URL** | `${ALITA_BASE_URL}` | Alita instance base URL |
| **Project ID** | `${ALITA_PROJECT_ID}` | Project ID for artifact storage |
| **API Key** | `${ALITA_API_KEY}` | Authentication token |
| **Tool** | `deleteFile` | Artifact tool to execute for file deletion |
| **Bucket Name** | `test-artifacts` | Target bucket for cleanup |

## Config

path: .alita\tool_configs\artifact-config.json
generateTestData: false

## Pre-requisites

- Alita instance is accessible and configured
- Valid API key with artifact delete permissions
- Bucket `test-artifacts` exists with test files
- User has permission to delete files in the bucket

## Test Steps & Expectations

### Step 1: Delete a Single File

Execute the `deleteFile` tool to remove one test file.

**Input:**
```json
{
  "filename": "test-document.txt",
  "bucket_name": "test-artifacts"
}
```

**Expectation:** The tool confirms successful deletion.

### Step 2: Verify File Deletion

List files to confirm the file was removed.

**Input:**
```json
{
  "bucket_name": "test-artifacts"
}
```

**Expectation:** The file list no longer includes `test-document.txt`.

### Step 3: Delete Multiple Files

Execute the `deleteFile` tool multiple times to clean up test files.

**Files to delete:**
- test-readme.md
- test-data.csv
- test-data.xlsx
- new-file.txt (if created)
- Sanitized filename from TC-002

**Expectation:** Each file is deleted successfully.

### Step 4: Attempt to Delete Non-Existent File

Execute the `deleteFile` tool on an already-deleted file.

**Input:**
```json
{
  "filename": "test-document.txt",
  "bucket_name": "test-artifacts"
}
```

**Expectation:** The tool returns an appropriate error message indicating the file doesn't exist.

### Step 5: Verify Bucket is Empty

List files to confirm all test files were removed.

**Input:**
```json
{
  "bucket_name": "test-artifacts"
}
```

**Expectation:** The file list is empty or shows only files not created during testing.

### Step 6: Clean Up TC-001 Temporary Buckets

Delete test files and buckets created in TC-001.

**Delete files from temp-bucket-2weeks:**
```json
{
  "filename": "test-file-1.txt",
  "bucket_name": "temp-bucket-2weeks"
}
```

**Delete files from temp-bucket-sanitize:**
```json
{
  "filename": "test-file-2.txt",
  "bucket_name": "temp-bucket-sanitize"
}
```

**Expectation:** All test files from TC-001 temporary buckets are deleted successfully.

### Step 7: Delete File from Default Bucket

Execute the `deleteFile` tool without specifying bucket_name.

**Input:**
```json
{
  "filename": "some-file.txt"
}
```

**Expectation:** The tool deletes the file from the default configured bucket.

## Post-Test Cleanup

### Cleanup Summary

This test case (TC-010) serves as the final cleanup for the entire artifact test suite:

1. **Default Bucket (`test-artifacts`):**
   - Deleted all files created in TC-002 through TC-009
   - Bucket remains (will auto-expire based on retention policy)
   - Can be reused for future test runs

2. **Temporary Buckets from TC-001:**
   - Deleted all test files from `temp-bucket-2weeks` and `temp-bucket-sanitize`
   - Buckets remain until manual deletion or expiration
   - Note: Bucket deletion tool not currently available in SDK

### Manual Cleanup (Optional)

If needed, delete temporary buckets through:
- Alita UI → Artifacts → Bucket Management
- Direct API calls to `/api/v2/artifacts/bucket/delete`
- Or wait for automatic expiration based on retention policies

**Buckets that may need manual deletion:**
- `temp-bucket-2weeks` (2 weeks retention)
- `temp-bucket-sanitize` (1 week retention)
