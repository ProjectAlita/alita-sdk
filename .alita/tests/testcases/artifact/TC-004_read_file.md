# Read File from Artifact

## Objective

Verify that the `readFile` tool correctly retrieves file content from an artifact bucket with various options.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Base URL** | `${ALITA_BASE_URL}` | Alita instance base URL |
| **Project ID** | `${ALITA_PROJECT_ID}` | Project ID for artifact storage |
| **API Key** | `${ALITA_API_KEY}` | Authentication token |
| **Tool** | `readFile` | Artifact tool to execute for reading files |
| **Bucket Name** | `test-artifacts` | Target bucket to read files from |

## Config

path: .alita\tool_configs\artifact-config.json
generateTestData: false

## Pre-requisites

- Alita instance is accessible and configured
- Valid API key with artifact read permissions
- Bucket `test-artifacts` exists with files created in TC-002
- User has permission to read files in the bucket

## Test Steps & Expectations

### Step 1: Read a Text File

Execute the `readFile` tool to read a simple text file.

**Input:**
```json
{
  "filename": "test-document.txt",
  "bucket_name": "test-artifacts"
}
```

**Expectation:** The tool returns the complete file content as a string matching the original content from TC-002.

### Step 2: Read a Markdown File

Execute the `readFile` tool to read the markdown file.

**Input:**
```json
{
  "filename": "test-readme.md",
  "bucket_name": "test-artifacts"
}
```

**Expectation:** The markdown content is returned correctly with all formatting preserved.

### Step 3: Read Excel File - All Sheets

Execute the `readFile` tool to read the Excel file with all sheets.

**Input:**
```json
{
  "filename": "test-data.xlsx",
  "bucket_name": "test-artifacts",
  "excel_by_sheets": true
}
```

**Expectation:** The tool returns data from both Sheet1 and Sheet2 in a structured format.

### Step 4: Read Excel File - Specific Sheet

Execute the `readFile` tool to read only a specific sheet from the Excel file.

**Input:**
```json
{
  "filename": "test-data.xlsx",
  "bucket_name": "test-artifacts",
  "sheet_name": "Sheet1"
}
```

**Expectation:** The tool returns only the data from Sheet1 (Name, Age, City table).

### Step 5: Read CSV File

Execute the `readFile` tool to read the CSV file.

**Input:**
```json
{
  "filename": "test-data.csv",
  "bucket_name": "test-artifacts"
}
```

**Expectation:** The CSV content is returned as plain text with proper line breaks.

### Step 6: Read Non-Existent File

Attempt to read a file that doesn't exist.

**Input:**
```json
{
  "filename": "non-existent-file.txt",
  "bucket_name": "test-artifacts"
}
```

**Expectation:** The tool returns an appropriate error message indicating the file was not found.
