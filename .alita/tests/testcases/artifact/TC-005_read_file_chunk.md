# Read File Chunk (Partial Read)

## Priority

Critical

## Objective

Verify that the `read_file_chunk` tool correctly reads specific line ranges from text files in an artifact bucket.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Tools Used** | `createNewBucket`, `createFile`, `read_file_chunk`, `deleteFile` | Tools for setup, verification, and cleanup |
| **Bucket Name** | `TC-005-read-file-chunk` | Dedicated bucket for this test (created if missing) |
| **Primary Input(s)** | `{{TC_005_MD_FILENAME}}={{RANDOM_STRING}}.md, {{TC_005_TXT_FILENAME}}={{RANDOM_STRING}}.txt` | Required and optional inputs derived from args_schema |

## Config

path: .alita\tool_configs\artifact-config.json
generateTestData: true

## Pre-requisites

- Alita instance is accessible and configured
- Valid API key with artifact read/write permissions
- User has permission to manage files and create buckets in the project
- Create bucket `TC-005-read-file-chunk` if missing. If it already exists, bucket creation must be treated as a non-error (idempotent).
- Ensure the bucket exists

Tool: `createNewBucket`

Input:
```json
{
  "bucket_name": "TC-005-read-file-chunk",
  "expiration_measure": "weeks",
  "expiration_value": 1
}
```

- Create files used for partial reads

Tool: `createFile`

Inputs:
{
  "filename": "{{TC_005_TXT_FILENAME}}",
  "filedata": "This is a test document for TC-005.\nLine 2: Testing partial reads.\nLine 3: More content here.\nLine 4: Final line.",
  "bucket_name": "TC-005-read-file-chunk"
}
```
```json
{
  "filename": "{{TC_005_MD_FILENAME}}",
  "filedata": "# TC-005 README\n\nThis is a markdown file used for chunk read verification.",
  "bucket_name": "TC-005-read-file-chunk"
}
```

## Test Steps & Expectations

### Step 1: Read First Two Lines

Execute the `read_file_chunk` tool to read lines 1-2 from the test document.

**Input:**
```json
{
  "file_path": "{{TC_005_TXT_FILENAME}}",
  "start_line": 1,
  "end_line": 2,
  "bucket_name": "TC-005-read-file-chunk"
}
```

**Expectation:** The tool returns only the first two lines:

```
This is a test document for TC-005.
Line 2: Testing partial reads.
```

### Step 2: Read Middle Lines

Execute the `read_file_chunk` tool to read lines 2-3.

**Input:**
```json
{
  "file_path": "{{TC_005_TXT_FILENAME}}",
  "start_line": 2,
  "end_line": 3,
  "bucket_name": "TC-005-read-file-chunk"
}
```

**Expectation:** The tool returns lines 2 and 3:
```
Line 2: Testing partial reads.
Line 3: More content here.
```

### Step 3: Read from Line to End

Execute the `read_file_chunk` tool without specifying end_line to read to the end of file.

**Input:**
```json
{
  "file_path": "{{TC_005_TXT_FILENAME}}",
  "start_line": 3,
  "bucket_name": "TC-005-read-file-chunk"
}
```

**Expectation:** The tool returns lines 3-4 (all remaining lines):
```
Line 3: More content here.
Line 4: Final line.
```

### Step 4: Read Single Line

Execute the `read_file_chunk` tool to read just one line.

**Input:**
```json
{
  "file_path": "{{TC_005_TXT_FILENAME}}",
  "start_line": 2,
  "end_line": 2,
  "bucket_name": "TC-005-read-file-chunk"
}
```

**Expectation:** The tool returns only line 2:
```
Line 2: Testing partial reads.
```

### Step 5: Read Markdown File Chunk

Execute the `read_file_chunk` tool on the markdown file.

**Input:**
```json
{
  "file_path": "{{TC_005_MD_FILENAME}}",
  "start_line": 1,
  "end_line": 3,
  "bucket_name": "TC-005-read-file-chunk"
}
```

**Expectation:** The tool returns the first 3 lines of the markdown file with formatting preserved.

### Step 6: Cleanup — Delete Created Files

Delete the files created during setup from `TC-005-read-file-chunk`. Buckets are intentionally left in place.

Tool: `deleteFile`

Inputs:
```json
{
  "filename": "{{TC_005_TXT_FILENAME}}",
  "bucket_name": "TC-005-read-file-chunk"
}
```
```json
{
  "filename": "{{TC_005_MD_FILENAME}}",
  "bucket_name": "TC-005-read-file-chunk"
}
```


Execute the `listFiles` tool to verify deletion.

**Input:**
```json
{
  "bucket_name": "TC-005-read-file-chunk"
}
```
`
**Expectation:** Verify that files `{{TC_005_MD_FILENAME}}`, `{{TC_005_TXT_FILENAME}}` do not exist in the bucket after listing.

