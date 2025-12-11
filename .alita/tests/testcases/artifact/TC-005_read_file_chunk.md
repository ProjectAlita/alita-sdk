# Read File Chunk (Partial Read)

## Objective

Verify that the `read_file_chunk` tool correctly reads specific line ranges from text files in an artifact bucket.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Base URL** | `${ALITA_BASE_URL}` | Alita instance base URL |
| **Project ID** | `${ALITA_PROJECT_ID}` | Project ID for artifact storage |
| **API Key** | `${ALITA_API_KEY}` | Authentication token |
| **Tool** | `read_file_chunk` | Artifact tool to execute for partial file reading |
| **Bucket Name** | `test-artifacts` | Target bucket to read files from |

## Config

path: .alita\tool_configs\artifact-config.json
generateTestData: false

## Pre-requisites

- Alita instance is accessible and configured
- Valid API key with artifact read permissions
- Bucket `test-artifacts` exists with text files created in TC-002
- File `test-document.txt` contains at least 4 lines

## Test Steps & Expectations

### Step 1: Read First Two Lines

Execute the `read_file_chunk` tool to read lines 1-2 from the test document.

**Input:**
```json
{
  "file_path": "test-document.txt",
  "start_line": 1,
  "end_line": 2,
  "bucket_name": "test-artifacts"
}
```

**Expectation:** The tool returns only the first two lines:
```
This is a test document.
Line 2: Testing partial reads.
```

### Step 2: Read Middle Lines

Execute the `read_file_chunk` tool to read lines 2-3.

**Input:**
```json
{
  "file_path": "test-document.txt",
  "start_line": 2,
  "end_line": 3,
  "bucket_name": "test-artifacts"
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
  "file_path": "test-document.txt",
  "start_line": 3,
  "bucket_name": "test-artifacts"
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
  "file_path": "test-document.txt",
  "start_line": 2,
  "end_line": 2,
  "bucket_name": "test-artifacts"
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
  "file_path": "test-readme.md",
  "start_line": 1,
  "end_line": 3,
  "bucket_name": "test-artifacts"
}
```

**Expectation:** The tool returns the first 3 lines of the markdown file with formatting preserved.
