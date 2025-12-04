# Get Page ID by Title

## Objective

Verify that the `get_page_id_by_title` tool correctly retrieves the page ID for a Confluence page using its title.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Space** | `AT` | Target Confluence space key |
| **Username** | `CONFLUENCE_USERNAME` | Confluence user email |
| **API Key** | `CONFLUENCE_API_KEY` | Confluence API token for authentication |
| **Base URL** | `https://epamelitea.atlassian.net/` | Confluence instance URL |
| **Tool** | `get_page_id_by_title` | Confluence tool to execute for getting page ID |
| **Title** | `Template - Project plan` | Title of the page to find |

## Config

path: .github\ai_native\testcases\confluence\configs\confluence-config.json
generateTestData: false

## Pre-requisites

- A Confluence space `AT` exists and is accessible
- Valid Confluence API token with read permissions
- A page with title `Template - Project plan` exists in the space

## Test Steps & Expectations

### Step 1: Execute the Tool

Execute the `get_page_id_by_title` tool with title parameter set to `Template - Project plan`.

**Expectation:** The tool runs without errors and returns the page ID.

### Step 2: Verify the Output

Verify that the output contains a valid page ID or error message if not found.

**Expectation:** The output is a page ID string (numeric) 104038676.
