# Index Data - Figma URL Validation

## Objective

Verify that the `index_data` tool correctly validates the `url` parameter, accepting only proper Figma file/page URLs and returning a clear, user-friendly error for invalid URLs.

## Test Data Configuration

### Settings

| Parameter   | Value           | Description                   |
|-------------|-----------------|-------------------------------|
| **Token**   | `FIGMA_TOKEN_1` | Figma personal access token   |
| **Tool**    | `index_data`    | Figma tool to execute         |

### Test Data

Use two types of URLs as input for the `url` parameter:

- **Valid Figma URL** (example):
  - `https://www.figma.com/file/<FILE_KEY>/Some-Design-Name`
  - `https://www.figma.com/design/<FILE_KEY>/Some-Design-Name?node-id=123-456`

- **Invalid Figma URL** (examples):
  - Missing scheme: `www.figma.com/file/<FILE_KEY>/Some-Design-Name`
  - Unsupported path: `https://www.figma.com/xyz/<FILE_KEY>/...`
  - Missing file key: `https://www.figma.com/file//Some-Design-Name`

## Config

path: .alita\tool_configs\figma-config.json
generateTestData : false

## Pre-requisites

- Figma API token is valid and has access to at least one file.
- A valid Figma file URL is available and follows one of the supported patterns:
  - `https://www.figma.com/file/<FILE_KEY>/...` or
  - `https://www.figma.com/design/<FILE_KEY>/...`.
- One or more invalid URLs are prepared that do **not** meet these requirements (e.g. missing protocol/host, wrong path segment, or missing file key).

## Test Steps & Expectations

### Step 1: Execute index_data with a valid Figma URL

List all your available tools you have.

Execute the `index_data` tool from the Figma toolkit with the `url` parameter set to a valid Figma file URL as described above. Use default values for other arguments.

**Expectation:** The tool runs without a validation error related to the URL. Indexing starts and returns one or more documents (or at least a non-empty response). No `ToolException` is raised complaining about the URL format.

### Step 2: Execute index_data with an invalid Figma URL

Execute the `index_data` tool again, this time with the `url` parameter set to an invalid Figma URL (for example, missing protocol/host or using an unsupported path such as `/xyz/` instead of `/file/` or `/design/`).

**Expectation:** The tool fails fast with a clear validation error about the URL format. The error message should explicitly mention the problem (such as missing protocol/host or unsupported path format) and refer to the expected patterns `/file/<FILE_KEY>/...` or `/design/<FILE_KEY>/...`. No indexing is performed for this invalid URL.
