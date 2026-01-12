# Create File in Artifact

## Priority

Critical

## Objective

Verify that the `createFile` tool correctly creates files in an artifact bucket, including text files and Excel files.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Tool** | `createFile` | Artifact tool to execute for creating files |
| **Bucket Name** | `test-artifacts` | Target bucket for file creation |
| **Primary Input(s)** | `{{TC_002_MD_FILENAME}}={{RANDOM_STRING}}.md, {{TC_002_TXT_FILENAME}}={{RANDOM_STRING}}.txt, {{TC_002_XLSX_FILENAME}}={{RANDOM_STRING}}.xlsx, {{TC_002_CSV_FILENAME}}={{RANDOM_STRING}}.csv,` | Required and optional inputs derived from args_schema |
- Create bucket `TC-002-create-file` if missing. If it already exists, bucket creation must be treated as a non-error (idempotent).
Tool: `createNewBucket`

Input:
```json
{
  "bucket_name": "tc-002-create-file",
  "expiration_measure": "weeks",
  "expiration_value": 1
}
```

## Config

path: .alita\tool_configs\artifact-config.json
generateTestData: true

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
  "filename": "{{TC_002_TXT_FILENAME}}",
  "filedata": "This is a test document.\nLine 2: Testing partial reads.\nLine 3: More content here.\nLine 4: Final line.",
  "bucket_name": "test-artifacts"
}
```

**Expectation:** The tool runs without errors and confirms file creation with a success message.

### Step 2: Read the Created Text File

Execute the `readFile` tool to read back the created text file.

**Input:**
```json
{
  "filename": "{{TC_002_TXT_FILENAME}}",
  "bucket_name": "test-artifacts"
}
```

**Expectation:** The output matches the original content used during file creation.

### Step 3: Create a Markdown File

Execute the `createFile` tool to create a markdown file.

**Input:**
```json
{
  "filename": "{{TC_002_MD_FILENAME}}",
  "filedata": "# Test README\n\n## Section 1\nContent for section 1.\n\n## Section 2\nContent for section 2.",
  "bucket_name": "test-artifacts"
}
```

**Expectation:** The markdown file is created successfully.

### Step 4: Read the Created Markdown File

Execute the `readFile` tool to read back the created markdown file.

**Input:**
```json
{
  "filename": "{{TC_002_MD_FILENAME}}",
  "bucket_name": "test-artifacts"
}
```

**Expectation:** The output matches the original markdown content used during file creation.

### Step 5: Create an Excel File

Execute the `createFile` tool to create an Excel file using JSON format.

**Input:**
```json
{
  "filename": "{{TC_002_XLSX_FILENAME}}",
  "filedata": "{\"Sheet1\": [[\"Name\", \"Age\", \"City\"], [\"Alice\", 25, \"New York\"], [\"Bob\", 30, \"San Francisco\"]], \"Sheet2\": [[\"Product\", \"Price\"], [\"Widget\", 19.99], [\"Gadget\", 29.99]]}",
  "bucket_name": "test-artifacts"
}
```

**Expectation:** The Excel file is created with two sheets containing the specified data.

### Step 6: Read the Created Excel File

Execute the `readFile` tool to read back the created Excel file.

**Input:**
```json
{
  "filename": "{{TC_002_XLSX_FILENAME}}",
  "bucket_name": "test-artifacts"
}
```

**Expectation:** The output contain content from original Excel data structure used during file creation.

### Step 7: Create a CSV File

Execute the `createFile` tool to create a CSV file.

**Input:**
```json
{
  "filename": "{{TC_002_CSV_FILENAME}}",
  "filedata": "Name,Email,Role\nJohn Doe,john@example.com,Developer\nJane Smith,jane@example.com,Designer\nBob Johnson,bob@example.com,Manager",
  "bucket_name": "test-artifacts"
}
```

**Expectation:** The CSV file is created successfully.

### Step 8: Read the Created CSV File

Execute the `readFile` tool to read back the created CSV file.

**Input:**
```json
{
  "filename": "{{TC_002_CSV_FILENAME}}",
  "bucket_name": "test-artifacts"
}
```

**Expectation:** The output matches the original CSV content used during file creation.

### Step 9: Verify Filename Sanitization

Create a file with special characters in the name.

**Input:**
```json
{
  "filename": "tc 002 special@file(name)#m4t2j8!.txt",
  "filedata": "Testing filename sanitization",
  "bucket_name": "test-artifacts"
}
```

**Expectation:** The file is created successfully.

### Step 10: Read the File with Special Characters

Execute the `readFile` tool to read back.

**Input:**
```json
{
  "filename": "tc-002-specialfilenamem4t2j8.txt",
  "bucket_name": "test-artifacts"
}
```

**Expectation:** The output matches the original content used during file creation, confirming that filename sanitization works correctly.

### Step 11: Cleanup Created Files

Execute the `deleteFile` tool to remove all files created during this test case.

**Input:**
```json
{
  "filename": "{{TC_002_MD_FILENAME}}",
  "bucket_name": "test-artifacts"
}
```
```json
{
  "filename": "{{TC_002_TXT_FILENAME}}",
  "bucket_name": "test-artifacts"
}
```
```json
{
  "filename": "{{TC_002_XLSX_FILENAME}}",
  "bucket_name": "test-artifacts"
}
```
```json
{
  "filename": "{{TC_002_CSV_FILENAME}}",
  "bucket_name": "test-artifacts"
}
```
```json
{
  "filename": "tc-002-specialfilenamem4t2j8.txt",
  "bucket_name": "test-artifacts"
}
```

Execute the `listFiles` tool to verify deletion.

**Input:**
```json
{
  "bucket_name": "test-artifacts"
}
```
`
**Expectation:** Verify that files `{{TC_002_MD_FILENAME}}`, `{{TC_002_TXT_FILENAME}}`, `{{TC_002_XLSX_FILENAME}}`, `{{TC_002_CSV_FILENAME}}`, and `tc-002-specialfilenamem4t2j8.txt` do not exist in the bucket after listing.

