# Get Page Tree with Multiple Descendants

## Objective

Verify that the `get_page_tree` tool correctly retrieves the complete hierarchical structure of a Confluence page including all descendant pages.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Space** | `AT` | Target Confluence space key |
| **Username** | `CONFLUENCE_USERNAME` | Confluence user email |
| **API Key** | `CONFLUENCE_API_KEY` | Confluence API token for authentication |
| **Base URL** | `https://epamelitea.atlassian.net/` | Confluence instance URL |
| **Tool** | `get_page_tree` | Confluence tool to execute for retrieving page tree |
| **Page ID** | Valid parent page ID | ID of the root page to retrieve tree from |

## Config

path: .github\ai_native\testcases\confluence\configs\confluence-config.json
generateTestData: false

## Pre-requisites

- A Confluence space `AT` exists and is accessible
- A parent page exists with known page ID `104038676`
- Valid Confluence API token with read permissions for the space
- Network access to the Confluence instance

## Test Steps & Expectations

### Step 1: Execute the Tool

Execute the `get_page_tree` tool with `104038676` page ID.

**Expectation:** The tool runs without errors and returns a success message.

### Step 2: Verify the Output

Verify that the output.

**Expectation:** The output is blank or {}.