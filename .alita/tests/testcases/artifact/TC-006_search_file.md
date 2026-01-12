# Search File Content

## Priority

Critical

## Objective

Verify that the `search_file` tool correctly searches for patterns in file content with context lines.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Tools Used** | `createNewBucket`, `createFile`, `search_file`, `deleteFile` | Tools required for setup, verification, and cleanup |
| **Bucket Name** | `TC-006-search-file` | Dedicated bucket for this test case (created if missing) |
| **Primary Input(s)** | `{{TC_006_MD_FILENAME}}={{RANDOM_STRING}}.md, {{TC_006_TXT_FILENAME}}={{RANDOM_STRING}}.txt, {{TC_006_CSV_FILENAME}}={{RANDOM_STRING}}.csv` | Required and optional inputs derived from args_schema |

## Config

path: .alita\tool_configs\artifact-config.json
generateTestData: true

## Pre-requisites

- Alita instance is accessible and configured
- Valid API key with artifact read/write permissions
- User has permission to manage files and create buckets in the project
- Create bucket `TC-006-search-file` if missing. If it already exists, bucket creation must be treated as a non-error (idempotent).
- Ensure the bucket exists

Tool: `createNewBucket`

Input:
```json
{
  "bucket_name": "TC-006-search-file",
  "expiration_measure": "weeks",
  "expiration_value": 1
}
```

- Create files to search

Tool: `createFile`

Inputs:
```json
{
  "filename": "{{TC_006_TXT_FILENAME}}",
  "filedata": "This is a test document for TC-006.\nLine 2: Testing partial reads.\nLine 3: More content here.\nLine 4: Final line.",
  "bucket_name": "TC-006-search-file"
}
```
```json
{
  "filename": "{{TC_006_MD_FILENAME}}",
  "filedata": "# TC-006 README\n\n## Section A\nIntro text.\n\n## Section B\nMore text.",
  "bucket_name": "TC-006-search-file"
}
```
```json
{
  "filename": "{{TC_006_CSV_FILENAME}}",
  "filedata": "email,age\njohn@example.com,31\njane@example.com,29",
  "bucket_name": "TC-006-search-file"
}
```

## Test Steps & Expectations

### Step 1: Search with Literal Text

Execute the `search_file` tool to search for literal text.

**Input:**
```json
{
  "file_path": "{{TC_006_TXT_FILENAME}}",
  "pattern": "partial reads",
  "is_regex": false,
  "context_lines": 1,
  "bucket_name": "TC-006-search-file"
}
```

**Expectation:** The tool returns the matching line with 1 line of context before and after:
  
```
Found 1 match(es) for pattern 'partial reads' in test-document.txt:

--- Match 1 at line 2 ---
  This is a test document for TC-006.
> Line 2: Testing partial reads.
  Line 3: More content here.
```

### Step 2: Search with Regex Pattern

Execute the `search_file` tool using a regex pattern.

**Input:**
```json
{
  "file_path": "test-document.txt",
  "pattern": "Line \\d+:",
  "is_regex": true,
  "context_lines": 0,
  "bucket_name": "TC-006-search-file"
}
```

**Expectation:** The tool returns all lines matching the pattern (lines 2, 3, 4) with no context.

### Step 3: Search Markdown Headers

Execute the `search_file` tool to find markdown headers.

**Input:**
```json
{
  "file_path": "test-readme.md",
  "pattern": "^##\\s+",
  "is_regex": true,
  "context_lines": 2,
  "bucket_name": "TC-006-search-file"
}
```

**Expectation:** The tool returns all level-2 headers with 2 lines of context.

### Step 4: Search CSV Data

Execute the `search_file` tool to find specific data in CSV.

**Input:**
```json
{
  "file_path": "test-data.csv",
  "pattern": "john@example.com",
  "is_regex": false,
  "context_lines": 1,
  "bucket_name": "TC-006-search-file"
}
```

**Expectation:** The tool returns the matching line with CSV header as context.

### Step 5: Search with No Matches

Execute the `search_file` tool with a pattern that doesn't exist.

**Input:**
```json
{
  "file_path": "test-document.txt",
  "pattern": "nonexistent pattern",
  "is_regex": false,
  "context_lines": 1,
  "bucket_name": "TC-006-search-file"
}
```

**Expectation:** The tool returns a message indicating no matches were found.

### Step 6: Case-Insensitive Search

Execute the `search_file` tool with case variation.

**Input:**
```json
{
  "file_path": "test-document.txt",
  "pattern": "TEST",
  "is_regex": false,
  "context_lines": 0,
  "bucket_name": "TC-006-search-file"
}
```

**Expectation:** The tool finds matches regardless of case (should match "test" and "Test").

### Cleanup — Delete Created Files (Bucket remains)

Delete the files created during setup from `TC-006-search-file`. Buckets are intentionally left in place.

Tool: `deleteFile`

Inputs:
```json
{
  "filename": "test-document.txt",
  "bucket_name": "TC-006-search-file"
}
```
```json
{
  "filename": "test-readme.md",
  "bucket_name": "TC-006-search-file"
}
```
```json
{
  "filename": "test-data.csv",
  "bucket_name": "TC-006-search-file"
}
```

**Expectation:** All specified files are deleted successfully or `None` response.
