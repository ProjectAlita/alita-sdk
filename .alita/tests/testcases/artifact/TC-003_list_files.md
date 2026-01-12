# List Files in Artifact

## Priority

Critical

## Objective

Verify that the `listFiles` tool correctly lists all files in an artifact bucket with API download links and expected metadata.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Primary Bucket Name** | `tc-003-list-files` | Dedicated bucket for this test case (created if missing) |
| **Tools Used** | `createNewBucket`, `createFile`, `listFiles`, `deleteFile` | Tools needed for setup, verification, and cleanup |
| **Primary Input(s)** | `{{TC_003_MD_FILENAME}}={{RANDOM_STRING}}.md, {{TC_003_TXT_FILENAME}}={{RANDOM_STRING}}.txt, {{TC_003_XLSX_FILENAME}}={{RANDOM_STRING}}.xlsx, {{TC_003_CSV_FILENAME}}={{RANDOM_STRING}}.csv,` | Required and optional inputs derived from args_schema |

## Config

path: .alita\tool_configs\artifact-config.json
generateTestData: true

## Pre-requisites

- Alita instance is accessible and configured
- Valid API key with artifact read/write permissions
- User has permission to manage files and create buckets in the project
- Buckets are NOT removed by this test; only files created during the test are deleted in cleanup
- Create bucket `tc-003-list-files` 
- If `tc-003-list-files` already exists, bucket creation must be treated as a non-error (idempotent).
- Create multiple files in `tc-003-list-files` that will be used to verify listing:
  - `{{TC_003_TXT_FILENAME}}`
  - `{{TC_003_MD_FILENAME}}`
  - `{{TC_003_XLSX_FILENAME}}`
  - `{{TC_003_CSV_FILENAME}}`

**Inputs:**
```json
{
  "filename": "{{TC_003_TXT_FILENAME}}",
  "filedata": "This is a test document for TC-003.\nSecond line.",
  "bucket_name": "tc-003-list-files"
}
```
```json
{
  "filename": "{{TC_003_MD_FILENAME}}",
  "filedata": "# TC-003 README\n\nThis is a markdown file used for list-files verification.",
  "bucket_name": "tc-003-list-files"
}
```
```json
{
  "filename": "{{TC_003_XLSX_FILENAME}}",
  "filedata": "{\"Sheet1\": [[\"ColA\", \"ColB\"], [\"Val1\", \"Val2\"]], \"Meta\": [[\"Key\", \"Value\"], [\"Run\", \"TC-003\"]]}",
  "bucket_name": "tc-003-list-files"
}
```
```json
{
  "filename": "{{TC_003_CSV_FILENAME}}",
  "filedata": "k1,k2\n1,2\n3,4",
  "bucket_name": "tc-003-list-files"
}
```

## Test Steps & Expectations

### Step 1: List Files in Bucket

Execute the `listFiles` tool to retrieve all files in the test bucket.

**Input:**
```json
{
  "bucket_name": "tc-003-list-files"
}
```

**Expectation:** The tool returns a list of files with, at minimum, the following fields per file:
- `name`
- `link` in format: `{base_url}/api/v2/artifacts/artifact/default/{project_id}/{bucket_name}/{filename}`
- `modified` (timestamp)
- `size` (bytes)

### Step 2: Verify File List Contents

Review the returned file list to ensure it contains the files created in Pre requisites:
  - `{{TC_003_TXT_FILENAME}}`
  - `{{TC_003_MD_FILENAME}}`
  - `{{TC_003_XLSX_FILENAME}}`
  - `{{TC_003_CSV_FILENAME}}`

**Expectation:** All created files are present in the listing with correct metadata.

### Step 3: Verify API Link Format

Check that each file has a properly formatted API download link.

**Expectation:** Each file should have a `link` field containing a valid URL like:
```
https://{BASE_URL}/api/v2/artifacts/artifact/default/{ALITA_PROJECT_ID}/tc-003-list-files/test-document.txt
```
And similarly for the other filenames returned.

### Step 6: List Files Using Default Bucket (No Input)

Execute the `listFiles` tool without specifying `bucket_name`. This should use the default bucket configured in the toolkit.

**Input:**
```json
{}
```

**Expectation:** The tool returns files from the default bucket. There should be no files.

### Step 7: Verify Empty Bucket Listing

Create a new, empty bucket and list its contents to verify that an empty result is returned.

**Create bucket input:**
```json
{
  "bucket_name": "tc-003-empty-bucket-{{RANDOM_STRING}}",
  "expiration_measure": "weeks",
  "expiration_value": 1
}
```

**List files input:**
```json
{
  "bucket_name": "tc-003-empty-bucket-{{RANDOM_STRING}}"
}
```

**Expectation:** The tool returns an empty list or an appropriate message indicating no files found. Buckets are not removed by this test.

### Step 8: Cleanup — Delete Created Files (Bucket remains)

Delete the files created from `tc-003-list-files`. Buckets are intentionally left in place.

**Inputs:**
```json
{
  "filename": "{{TC_003_TXT_FILENAME}}",
  "bucket_name": "tc-003-list-files"
}
```
```json
{
  "filename": "{{TC_003_MD_FILENAME}}",
  "bucket_name": "tc-003-list-files"
}
```
```json
{
  "filename": "{{TC_003_XLSX_FILENAME}}",
  "bucket_name": "tc-003-list-files"
}
```
```json
{
  "filename": "{{TC_003_CSV_FILENAME}}",
  "bucket_name": "tc-003-list-files"
}
```

Execute the `listFiles` tool to verify deletion.

**Input:**
```json
{
  "bucket_name": "tc-003-list-files"
}
```
`
**Expectation:** Verify that files `{{TC_003_MD_FILENAME}}`, `{{TC_003_TXT_FILENAME}}`, `{{TC_003_XLSX_FILENAME}}`, and `{{TC_003_CSV_FILENAME}}` do not exist in the bucket after listing.