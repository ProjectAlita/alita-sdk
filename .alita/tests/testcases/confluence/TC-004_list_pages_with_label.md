# List Pages with Label

## Objective

Verify that the `list_pages_with_label` tool correctly retrieves a list of page IDs and titles for pages tagged with a specific label.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Space** | `AT` | Target Confluence space key |
| **Base URL** | `https://epamelitea.atlassian.net/` | Confluence instance URL |
| **Tool** | `list_pages_with_label` | Confluence tool to execute for listing labeled pages |
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

Execute the `list_pages_with_label` tool with the label parameter set to `test-label`.

**Expectation:** The tool runs without errors and returns a list of pages.

### Step 2: Verify the Output

Verify that the output contains a list of dictionaries with 'id' and 'title' keys.

**Expectation:** The output contains this content `[{'id': '138969168', 'title': 'TC-003 Page with label'}]` contextually.