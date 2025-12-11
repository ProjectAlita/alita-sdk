# Create File in Artifact

## Objective

Verify that the `createFile` tool correctly creates files in an artifact bucket, including text files and Excel files.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Base URL** | `${ALITA_BASE_URL}` | Alita instance base URL |
| **Project ID** | `${ALITA_PROJECT_ID}` | Project ID for artifact storage |
| **API Key** | `${ALITA_API_KEY}` | Authentication token |
| **Tool** | `createFile` | Artifact tool to execute for creating files |
| **Bucket Name** | `test-artifacts` | Target bucket for file creation |

## Config

path: .alita\tool_configs\artifact-config.json
generateTestData: false

## Pre-requisites

- Alita instance is accessible and configured
- Valid API key with artifact write permissions
- Bucket `test-artifacts` exists (created in TC-001)
- User has permission to create files in the bucket

## Test Steps & Expectations

### Step 1: Create a Text File

Execute the `createFile` tool to create a simple text file.

**Input:**
```json
{
  "filename": "test-document.txt",
  "filedata": "This is a test document.\nLine 2: Testing partial reads.\nLine 3: More content here.\nLine 4: Final line.",
  "bucket_name": "test-artifacts"
}
```

**Expectation:** The tool runs without errors and confirms file creation with a success message.

### Step 2: Create a Markdown File

Execute the `createFile` tool to create a markdown file.

**Input:**
```json
{
  "filename": "test-readme.md",
  "filedata": "# Test README\n\n## Section 1\nContent for section 1.\n\n## Section 2\nContent for section 2.",
  "bucket_name": "test-artifacts"
}
```

**Expectation:** The markdown file is created successfully.

### Step 3: Create an Excel File

Execute the `createFile` tool to create an Excel file using JSON format.

**Input:**
```json
{
  "filename": "test-data.xlsx",
  "filedata": "{\"Sheet1\": [[\"Name\", \"Age\", \"City\"], [\"Alice\", 25, \"New York\"], [\"Bob\", 30, \"San Francisco\"]], \"Sheet2\": [[\"Product\", \"Price\"], [\"Widget\", 19.99], [\"Gadget\", 29.99]]}",
  "bucket_name": "test-artifacts"
}
```

**Expectation:** The Excel file is created with two sheets containing the specified data.

### Step 4: Create a CSV File

Execute the `createFile` tool to create a CSV file.

**Input:**
```json
{
  "filename": "test-data.csv",
  "filedata": "Name,Email,Role\nJohn Doe,john@example.com,Developer\nJane Smith,jane@example.com,Designer\nBob Johnson,bob@example.com,Manager",
  "bucket_name": "test-artifacts"
}
```

**Expectation:** The CSV file is created successfully.

### Step 5: Verify Filename Sanitization

Create a file with special characters in the name.

**Input:**
```json
{
  "filename": "test file@#$%with&special*chars.txt",
  "filedata": "Testing filename sanitization",
  "bucket_name": "test-artifacts"
}
```

**Expectation:** The file is created with a sanitized filename (special characters removed or replaced).
