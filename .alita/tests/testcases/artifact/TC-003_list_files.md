# List Files in Artifact

## Objective

Verify that the `listFiles` tool correctly lists all files in an artifact bucket with API download links.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Base URL** | `${ALITA_BASE_URL}` | Alita instance base URL |
| **Project ID** | `${ALITA_PROJECT_ID}` | Project ID for artifact storage |
| **API Key** | `${ALITA_API_KEY}` | Authentication token |
| **Tool** | `listFiles` | Artifact tool to execute for listing files |
| **Bucket Name** | `test-artifacts` | Target bucket to list files from |

## Config

path: .alita\tool_configs\artifact-config.json
generateTestData: false

## Pre-requisites

- Alita instance is accessible and configured
- Valid API key with artifact read permissions
- Bucket `test-artifacts` exists with files created in TC-002
- User has permission to list files in the bucket

## Test Steps & Expectations

### Step 1: List Files in Bucket

Execute the `listFiles` tool to retrieve all files in the test bucket.

**Input:**
```json
{
  "bucket_name": "test-artifacts"
}
```

**Expectation:** The tool returns a list of files with the following information for each file:
- File name
- API download link in format: `{base_url}/api/v2/artifacts/artifact/default/{project_id}/{bucket_name}/{file_name}`
- Modified timestamp
- File size

### Step 2: Verify File List Contents

Review the returned file list to ensure it contains the files created in TC-002.

**Expectation:** The list should include:
- `test-document.txt`
- `test-readme.md`
- `test-data.xlsx`
- `test-data.csv`
- Sanitized filename from Step 5 of TC-002

### Step 3: Verify API Link Format

Check that each file has a properly formatted API download link.

**Expectation:** Each file should have a `link` field containing a valid URL like:
```
https://your-server.com/api/v2/artifacts/artifact/default/123/test-artifacts/test-document.txt
```

### Step 4: List Files in Default Bucket

Execute the `listFiles` tool without specifying bucket_name (should use default from config).

**Input:**
```json
{}
```

**Expectation:** The tool returns files from the default bucket configured in the toolkit.

### Step 5: Verify Empty Bucket

Create a new empty bucket and list its contents.

**Expectation:** The tool returns an empty list or appropriate message indicating no files found.
