# Get Pages with Label

## Objective

Verify that the `get_pages_with_label` tool correctly retrieves pages tagged with a specific label in the Confluence space.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Space** | `AT` | Target Confluence space key |
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

Verify that the output contains page details including page_id, page_title, page_url, content field must be not blank.

**Expectation:** The output contains `[
  {
    "page_id": "138969168",
    "page_title": "TC-003 Page with label",
    "page_url": "https://epamelitea.atlassian.net/spaces/AT/pages/138969168/TC-003+Page+with+label",
    "content": "ANY NON-BLANK CONTENT"
  }
]`