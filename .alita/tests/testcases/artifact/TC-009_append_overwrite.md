# Append and Overwrite Data

## Objective

Verify that the `appendData` and `overwriteData` tools correctly modify file contents in artifact buckets.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Base URL** | `${ALITA_BASE_URL}` | Alita instance base URL |
| **Project ID** | `${ALITA_PROJECT_ID}` | Project ID for artifact storage |
| **API Key** | `${ALITA_API_KEY}` | Authentication token |
| **Tools** | `appendData`, `overwriteData` | Artifact tools for data modification |
| **Bucket Name** | `test-artifacts` | Target bucket for operations |

## Config

path: .alita\tool_configs\artifact-config.json
generateTestData: false

## Pre-requisites

- Alita instance is accessible and configured
- Valid API key with artifact write permissions
- Bucket `test-artifacts` exists with test files
- Original files available for modification

## Test Steps & Expectations

### Step 1: Append Data to Text File

Execute the `appendData` tool to add content to an existing file.

**Input:**
```json
{
  "filename": "test-document.txt",
  "filedata": "\nLine 5: Appended content.\nLine 6: More appended data.",
  "bucket_name": "test-artifacts"
}
```

**Expectation:** The tool successfully appends the data and confirms with a success message.

### Step 2: Verify Append Operation

Read the file to confirm data was appended.

**Input:**
```json
{
  "filename": "test-document.txt",
  "bucket_name": "test-artifacts"
}
```

**Expectation:** The file now contains the original 4 lines plus the 2 appended lines (total 6 lines).

### Step 3: Append to CSV File

Execute the `appendData` tool to add a new row to the CSV.

**Input:**
```json
{
  "filename": "test-data.csv",
  "filedata": "\nAlice Brown,alice@example.com,Engineer",
  "bucket_name": "test-artifacts"
}
```

**Expectation:** The new row is appended to the CSV file.

### Step 4: Overwrite File Content

Execute the `overwriteData` tool to replace entire file content.

**Input:**
```json
{
  "filename": "test-document.txt",
  "filedata": "Completely new content.\nAll previous data replaced.\nThis is the new file.",
  "bucket_name": "test-artifacts"
}
```

**Expectation:** The tool successfully overwrites the file and confirms with a success message.

### Step 5: Verify Overwrite Operation

Read the file to confirm it was completely replaced.

**Input:**
```json
{
  "filename": "test-document.txt",
  "bucket_name": "test-artifacts"
}
```

**Expectation:** The file contains only the new content (3 lines), all previous content is gone.

### Step 6: Overwrite Markdown File

Execute the `overwriteData` tool to replace markdown content.

**Input:**
```json
{
  "filename": "test-readme.md",
  "filedata": "# Updated README\n\nThis file has been completely rewritten.\n\n## New Structure\n- Point 1\n- Point 2",
  "bucket_name": "test-artifacts"
}
```

**Expectation:** The markdown file is completely replaced with new structure.

### Step 7: Append to Non-Existent File

Execute the `appendData` tool on a file that doesn't exist.

**Input:**
```json
{
  "filename": "new-file.txt",
  "filedata": "Creating new file via append",
  "bucket_name": "test-artifacts"
}
```

**Expectation:** The tool creates the file with the provided content (append on empty/new file).

### Step 8: Overwrite with Empty Content

Execute the `overwriteData` tool with empty string.

**Input:**
```json
{
  "filename": "test-document.txt",
  "filedata": "",
  "bucket_name": "test-artifacts"
}
```

**Expectation:** The file is replaced with an empty file (0 bytes or minimal content).
