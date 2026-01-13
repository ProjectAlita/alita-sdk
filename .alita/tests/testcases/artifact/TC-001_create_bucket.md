# Create New Bucket

## Priority

Critical

## Objective

Verify that the `createNewBucket` tool correctly creates a new artifact bucket with specified expiration settings.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Tool** | `createNewBucket` | Artifact tool to execute for creating a new bucket |

## Config

path: .alita/tool_configs/artifact-config.json
generateTestData: true

## Pre-requisites

- Alita instance is accessible and configured
- Valid API key with artifact management permissions
- User has permission to create buckets in the specified project
- Generate unique variables using `TC-001_TEST_BUCKET_PREFIX` and a timestamp or short random suffix to avoid collisions with previous runs. Example generated values:
  - `TC-001_BUCKET_A = {{TC-001_TEST_BUCKET_PREFIX}}-20260109-1234-2weeks`
  - `TC-001_BUCKET_B_RAW = {{TC-001_TEST_BUCKET_PREFIX}}_20260109_1234_sanitize`
  - `TC-001_BUCKET_B = {{TC-001_TEST_BUCKET_PREFIX}}-20260109-1234-sanitize` 

**DO NOT CREATE THE BUCKETS YOURSELF;** the test steps will handle bucket creation.

## Test Steps & Expectations

### Step 1: Execute the Tool

Execute the `createNewBucket` tool to create a new bucket with 2 weeks expiration.

**Input:**
```json
{
  "bucket_name": "{{TC-001_BUCKET_A}}",
  "expiration_measure": "weeks",
  "expiration_value": 2
}
```

**Expectation:** The tool runs without errors and confirms bucket creation.

### Step 2: Verify Bucket Name Validation

Attempt to create a bucket with underscores in the name.

**Input:**
```json
{
  "bucket_name": "{{TC-001_BUCKET_B_RAW}}",
  "expiration_measure": "weeks",
  "expiration_value": 1
}
```

**Expectation:** The tool should handle the invalid name appropriately by converting underscores to hyphens (resulting in `{{TC-001_BUCKET_B}}`).

### Step 3: Create Test Files in Temporary Buckets

Create test files in both temporary buckets to verify file operations before cleanup.

**For temp-bucket-2weeks:**
```json
{
  "filename": "test-file-1.txt",
  "filedata": "This is test content for bucket 1",
  "bucket_name": "{{TC-001_BUCKET_A}}"
}
```

**For temp-bucket-sanitize:**
```json
{
  "filename": "test-file-2.txt",
  "filedata": "This is test content for bucket 2",
  "bucket_name": "{{TC-001_BUCKET_B}}"
}
```

**Expectation:** Both files are created successfully in their respective buckets.

### Step 4: Clean Up - Delete Test Files

Delete the test files created in Step 3.

**Delete from temp-bucket-2weeks:**
```json
{
  "filename": "test-file-1.txt",
  "bucket_name": "{{TC-001_BUCKET_A}}"
}
```

**Delete from temp-bucket-sanitize:**
```json
{
  "filename": "test-file-2.txt",
  "bucket_name": "{{TC-001_BUCKET_B}}"
}
```

**Expectation:** Verify success messages for files `test-file-1.txt` and `test-file-2.txt` deletion.