# Create New Bucket

## Objective

Verify that the `createNewBucket` tool correctly creates a new artifact bucket with specified expiration settings.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Base URL** | `${ALITA_BASE_URL}` | Alita instance base URL |
| **Project ID** | `${ALITA_PROJECT_ID}` | Project ID for artifact storage |
| **API Key** | `${ALITA_API_KEY}` | Authentication token |
| **Tool** | `createNewBucket` | Artifact tool to execute for creating a new bucket |
| **Test Bucket 1** | `temp-bucket-2weeks` | Temporary bucket to test creation with 2 weeks expiration |
| **Test Bucket 2** | `temp_bucket_sanitize` | Temporary bucket to test name sanitization (underscores) |
| **Expiration Measure** | `weeks` | Time measure for bucket expiration (days/weeks/months/years) |
| **Expiration Value** | `2` | Number of time units before expiration |

## Config

path: .alita\tool_configs\artifact-config.json
generateTestData: false

## Pre-requisites

- Alita instance is accessible and configured
- Valid API key with artifact management permissions
- User has permission to create buckets in the specified project
- Default bucket `test-artifacts` is auto-created by the toolkit (NOT tested in this case)
- Test buckets `temp-bucket-2weeks` and `temp-bucket-sanitize` should NOT already exist
- If test buckets exist from previous runs, they should be deleted first
- Bucket names follow naming rules (lowercase, hyphens allowed, underscores auto-converted)

## Test Steps & Expectations

### Step 1: Execute the Tool

Execute the `createNewBucket` tool to create a new bucket with 2 weeks expiration.

**Input:**
```json
{
  "bucket_name": "temp-bucket-2weeks",
  "expiration_measure": "weeks",
  "expiration_value": 2
}
```

**Expectation:** The tool runs without errors and confirms bucket creation.

### Step 2: Verify Bucket Creation

List available buckets to confirm the new bucket exists.

**Expectation:** The bucket `temp-bucket-2weeks` appears in the list with correct expiration settings (2 weeks).

### Step 3: Verify Bucket Name Validation

Attempt to create a bucket with underscores in the name.

**Input:**
```json
{
  "bucket_name": "temp_bucket_sanitize",
  "expiration_measure": "weeks",
  "expiration_value": 1
}
```

**Expectation:** The tool should handle the invalid name appropriately by converting underscores to hyphens (resulting in `temp-bucket-sanitize`).

### Step 4: Create Test Files in Temporary Buckets

Create test files in both temporary buckets to verify file operations before cleanup.

**For temp-bucket-2weeks:**
```json
{
  "filename": "test-file-1.txt",
  "filedata": "This is test content for bucket 1",
  "bucket_name": "temp-bucket-2weeks"
}
```

**For temp-bucket-sanitize:**
```json
{
  "filename": "test-file-2.txt",
  "filedata": "This is test content for bucket 2",
  "bucket_name": "temp-bucket-sanitize"
}
```

**Expectation:** Both files are created successfully in their respective buckets.

### Step 5: Clean Up - Delete Test Files

Delete the test files created in Step 4.

**Delete from temp-bucket-2weeks:**
```json
{
  "filename": "test-file-1.txt",
  "bucket_name": "temp-bucket-2weeks"
}
```

**Delete from temp-bucket-sanitize:**
```json
{
  "filename": "test-file-2.txt",
  "bucket_name": "temp-bucket-sanitize"
}
```

**Expectation:** Both files are deleted successfully. Listing files in each bucket should return empty results.

### Step 6: Clean Up - Delete Temporary Buckets

Delete both temporary buckets created during this test.

**Note:** The Alita SDK artifact toolkit does not currently expose a `deleteBucket` tool through the standard API. Bucket deletion should be performed manually through the Alita UI or API if needed, or buckets can be left to expire based on their retention policy.

**Expected Behavior:** 
- If a `deleteBucket` tool becomes available, use it to delete `temp-bucket-2weeks` and `temp-bucket-sanitize`
- If not available, document that manual cleanup is required or buckets will auto-expire
- The default bucket `test-artifacts` should remain untouched
