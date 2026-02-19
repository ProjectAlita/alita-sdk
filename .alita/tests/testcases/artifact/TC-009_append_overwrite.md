# Append Data

## Objective

Verify that the `appendData` tool correctly modifies file contents in artifact buckets.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Tools** | `appendData`, `readFile` | Artifact tools for data modification |
| **Bucket Name** | `TC-009-append-overwrite` | Target bucket for operations |
| **Primary Input(s)** | `{{TC_009_TXT_FILENAME}}={{RANDOM_STRING}}.txt, {{TC_009_NON_EXISTENT_FILENAME}}={{RANDOM_STRING}}.txt, {{TC_009_CSV_FILENAME}}={{RANDOM_STRING}}.csv,` | Required and optional inputs derived from args_schema |

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

### Step 5: Append to Non-Existent File

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

### Step 6: Verify Append on Non-Existent File

Read the file to confirm it was created with the appended content.

**Input:**
```json
{
  "filename": "{{TC_009_NON_EXISTENT_FILENAME}}",
  "bucket_name": "tc-009-append-overwrite"
}
```

**Expectation:** The file contains one line `Creating new file via append`.

### Step 7: Cleanup — Delete Created Files (Bucket remains)

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
  "filename": "{{TC_009_CSV_FILENAME}}",
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

Execute the `listFiles` tool to verify deletion.

**Input:**
```json
{
  "bucket_name": "tc-009-append-overwrite"
}
```
`
**Expectation:** Verify that files `{{TC_009_MD_FILENAME}}`, `{{TC_009_TXT_FILENAME}}`, `{{TC_009_NON_EXISTENT_FILENAME}}`, and `{{TC_009_CSV_FILENAME}}` do not exist in the bucket after listing.

