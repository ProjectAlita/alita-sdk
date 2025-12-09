# Get Pages with Label

## Objective

Verify that the `get_pages_with_label` tool correctly retrieves pages tagged with a specific label in the Confluence space.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Space** | `AT` | Target Confluence space key |
| **Username** | `CONFLUENCE_USERNAME` | Confluence user email |
| **API Key** | `CONFLUENCE_API_KEY` | Confluence API token for authentication |
| **Tool** | `get_pages_with_label` | Confluence tool to execute for retrieving labeled pages |
| **Label** | `test-label` | Label to filter pages |

## Config

path: .alita\tool_configs\confluence-config.json
generateTestData: false

## Pre-requisites

- A Confluence space `AT` exists and is accessible
- Valid Confluence API token with read permissions
- At least one page exists with the label `test-label`

## Test Steps & Expectations

### Step 1: Execute the Tool

Execute the `get_pages_with_label` tool with the label parameter set to `test-label`.

**Expectation:** The tool runs without errors and returns page information.

### Step 2: Verify the Output

Verify that the output contains page details including page_id, page_title, page_url, content.

**Expectation:** The output contains `[
  {
    "page_id": "104300545",
    "page_title": "Test Label Page",
    "page_url": "https://epamelitea.atlassian.net/spaces/AT/pages/104300545/Test+Label+Page",
    "content": ""
  }
]` .
