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
| **Test Bucket Prefix** | `{{TC-001_TEST_BUCKET_PREFIX}}` | Prefix for generated test buckets (recommend: `temp-bucket`) |
| **Generated Bucket A** | `{{TC-001_BUCKET_A}}` | Generated bucket name for the 2-weeks retention scenario (prefix + timestamp + `-2weeks`) |
| **Generated Bucket B (raw)** | `{{TC-001_BUCKET_B_RAW}}` | Generated bucket name containing underscores to test sanitization (prefix + `_` + timestamp + `_sanitize`) |
| **Sanitized Bucket B** | `{{TC-001_BUCKET_B}}` | Expected sanitized version of `{{TC-001_BUCKET_B_RAW}}` (underscores -> hyphens) |
| **Expiration Measure** | `weeks` | Time measure for bucket expiration (days/weeks/months/years) |
| **Expiration Value A** | `2` | Number of time units before expiration for bucket A |
| **Expiration Value B** | `1` | Number of time units before expiration for bucket B |

## Config

path: .alita/tool_configs/artifact-config.json
generateTestData: true

## Pre-requisites

- Alita instance is accessible and configured
- Valid API key with artifact management permissions
- User has permission to create buckets in the specified project
- The test MUST generate unique bucket names using `{{TC-001_TEST_BUCKET_PREFIX}}` and a timestamp or short random suffix to avoid collisions with previous runs. Example generated values:
  - `{{TC-001_BUCKET_A}} = {{TC-001_TEST_BUCKET_PREFIX}}-20260109-1234-2weeks`
  - `{{TC-001_BUCKET_B_RAW}} = {{TC-001_TEST_BUCKET_PREFIX}}_20260109_1234_sanitize`
  - `{{TC-001_BUCKET_B}} = {{TC-001_TEST_BUCKET_PREFIX}}-20260109-1234-sanitize`

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

### Step 2: Verify Bucket Creation

Refer to Step 1's created bucket.

**Expectation:** The bucket `{{TC-001_BUCKET_A}}` appears in message.

### Step 3: Verify Bucket Name Validation

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

### Step 4: Create Test Files in Temporary Buckets

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

### Step 5: Clean Up - Delete Test Files

Delete the test files created in Step 4.

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

Execute the `listFiles` tool for each bucket to verify deletion.

**Input:**
```json
{
  "bucket_name": "{{TC-001_BUCKET_A}}"
}
```

**Input:**
```json
{
  "bucket_name": "{{TC-001_BUCKET_B}}"
}
```

**Expectation:** Verify that files `test-file-1.txt` and `test-file-2.txt` do not exist in both buckets after listing.
