# Search by Title

## Objective

Verify that the `search_by_title` tool correctly searches for Confluence pages by query text in the page title only.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Space** | `AT` | Target Confluence space key |
| **Base URL** | `https://epamelitea.atlassian.net/` | Confluence instance URL |
| **Tool** | `search_by_title` | Confluence tool to execute for title-based search |
| **Query** | `Test Label Page` | Search query text for title |

## Config

path: .alita\tool_configs\confluence-config.json
generateTestData: false

## Pre-requisites

- A Confluence space `MFS` exists and is accessible
- Valid Confluence API token with read permissions
- At least one page exists with `Test Label Page` in the title

## Test Steps & Expectations

### Step 1: Execute the Tool

Execute the `search_by_title` tool with query parameter set to `Test Label Page`.

**Expectation:** The tool runs without errors and returns search results.

### Step 2: Verify the Output

Verify that the output contains page information for pages with matching titles.

**Expectation:** The output is a string containing page details (page_id, page_title, page_url, content) for pages with titles matching the query.
