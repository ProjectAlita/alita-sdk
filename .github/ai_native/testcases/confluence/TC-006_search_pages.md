# Search Pages

## Objective

Verify that the `search_pages` tool correctly searches for pages in Confluence by query text in title or page content.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Space** | `AT` | Target Confluence space key |
| **Username** | `CONFLUENCE_USERNAME` | Confluence user email |
| **API Key** | `CONFLUENCE_API_KEY` | Confluence API token for authentication |
| **Base URL** | `https://epamelitea.atlassian.net/` | Confluence instance URL |
| **Tool** | `search_pages` | Confluence tool to execute for searching pages |
| **Query** | `test` | Search query text |

## Config

path: .github\ai_native\testcases\confluence\configs\confluence-config.json
generateTestData: false

## Pre-requisites

- A Confluence space `AT` exists and is accessible
- Valid Confluence API token with read permissions
- At least one page exists containing the word `test` in title or content

## Test Steps & Expectations

### Step 1: Execute the Tool

Execute the `search_pages` tool with query parameter set to `test`.

**Expectation:** The tool runs without errors and returns search results.

### Step 2: Verify the Output

Verify that the output contains page information matching the search query.

**Expectation:** The output is a string containing page details (page_id, page_title, page_url, content) for pages matching the query, or an error message if no results found.
