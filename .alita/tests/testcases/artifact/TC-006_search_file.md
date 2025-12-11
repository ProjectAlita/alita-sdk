# Search File Content

## Objective

Verify that the `search_file` tool correctly searches for patterns in file content with context lines.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Base URL** | `${ALITA_BASE_URL}` | Alita instance base URL |
| **Project ID** | `${ALITA_PROJECT_ID}` | Project ID for artifact storage |
| **API Key** | `${ALITA_API_KEY}` | Authentication token |
| **Tool** | `search_file` | Artifact tool to execute for searching files |
| **Bucket Name** | `test-artifacts` | Target bucket to search files in |

## Config

path: .alita\tool_configs\artifact-config.json
generateTestData: false

## Pre-requisites

- Alita instance is accessible and configured
- Valid API key with artifact read permissions
- Bucket `test-artifacts` exists with files created in TC-002
- Files contain searchable text content

## Test Steps & Expectations

### Step 1: Search with Literal Text

Execute the `search_file` tool to search for literal text.

**Input:**
```json
{
  "file_path": "test-document.txt",
  "pattern": "partial reads",
  "is_regex": false,
  "context_lines": 1,
  "bucket_name": "test-artifacts"
}
```

**Expectation:** The tool returns the matching line with 1 line of context before and after:
```
Found 1 match(es) for pattern 'partial reads' in test-document.txt:

--- Match 1 at line 2 ---
  This is a test document.
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
  "bucket_name": "test-artifacts"
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
  "bucket_name": "test-artifacts"
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
  "bucket_name": "test-artifacts"
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
  "bucket_name": "test-artifacts"
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
  "bucket_name": "test-artifacts"
}
```

**Expectation:** The tool finds matches regardless of case (should match "test" and "Test").
