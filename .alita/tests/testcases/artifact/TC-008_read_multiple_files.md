# Read Multiple Files in Batch

## Objective

Verify that the `read_multiple_files` tool correctly reads multiple files in a single operation.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Base URL** | `${ALITA_BASE_URL}` | Alita instance base URL |
| **Project ID** | `${ALITA_PROJECT_ID}` | Project ID for artifact storage |
| **API Key** | `${ALITA_API_KEY}` | Authentication token |
| **Tool** | `read_multiple_files` | Artifact tool to execute for batch reading |
| **Bucket Name** | `test-artifacts` | Target bucket containing files |

## Config

path: .alita\tool_configs\artifact-config.json
generateTestData: false

## Pre-requisites

- Alita instance is accessible and configured
- Valid API key with artifact read permissions
- Bucket `test-artifacts` exists with multiple text files
- Files created in TC-002 are available

## Test Steps & Expectations

### Step 1: Read Multiple Text Files

Execute the `read_multiple_files` tool to read several text files at once.

**Input:**
```json
{
  "file_paths": ["test-document.txt", "test-readme.md", "test-data.csv"],
  "bucket_name": "test-artifacts"
}
```

**Expectation:** The tool returns a dictionary mapping each file path to its content:
```json
{
  "test-document.txt": "This is a test document.\n...",
  "test-readme.md": "# Test README\n...",
  "test-data.csv": "Name,Email,Role\n..."
}
```

### Step 2: Read Multiple Files with Partial Read

Execute the `read_multiple_files` tool with offset and limit parameters.

**Input:**
```json
{
  "file_paths": ["test-document.txt", "test-readme.md"],
  "offset": 1,
  "limit": 2,
  "bucket_name": "test-artifacts"
}
```

**Expectation:** Both files return only lines 1-2 of their content.

### Step 3: Read Mix of Valid and Invalid Files

Execute the `read_multiple_files` tool with some files that don't exist.

**Input:**
```json
{
  "file_paths": ["test-document.txt", "nonexistent.txt", "test-readme.md"],
  "bucket_name": "test-artifacts"
}
```

**Expectation:** The tool returns content for valid files and error messages for invalid ones:
```json
{
  "test-document.txt": "This is a test document.\n...",
  "nonexistent.txt": "Error reading file: File not found",
  "test-readme.md": "# Test README\n..."
}
```

### Step 4: Read Empty File List

Execute the `read_multiple_files` tool with an empty file list.

**Input:**
```json
{
  "file_paths": [],
  "bucket_name": "test-artifacts"
}
```

**Expectation:** The tool returns an empty dictionary or appropriate validation error.

### Step 5: Read Large Number of Files

Execute the `read_multiple_files` tool with many files to test batch performance.

**Input:**
```json
{
  "file_paths": ["test-document.txt", "test-readme.md", "test-data.csv", "test-data.xlsx"],
  "bucket_name": "test-artifacts"
}
```

**Expectation:** All files are read successfully and returned in the dictionary, including the Excel file parsed as text.
