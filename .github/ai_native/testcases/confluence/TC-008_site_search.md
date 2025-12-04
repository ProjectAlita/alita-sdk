# Site Search

## Objective

Verify that the `site_search` tool correctly performs a site-wide search in Confluence using the siteSearch CQL operator.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Space** | `AT` | Target Confluence space key |
| **Username** | `CONFLUENCE_USERNAME` | Confluence user email |
| **API Key** | `CONFLUENCE_API_KEY` | Confluence API token for authentication |
| **Base URL** | `https://epamelitea.atlassian.net/` | Confluence instance URL |
| **Tool** | `site_search` | Confluence tool to execute for site search |
| **Query** | `test` | Search query text |

## Config

path: .github\ai_native\testcases\confluence\configs\confluence-config.json
generateTestData: false

## Pre-requisites

- A Confluence space `AT` exists and is accessible
- Valid Confluence API token with read permissions
- At least one page exists that matches the search query `test`

## Test Steps & Expectations

### Step 1: Execute the Tool

Execute the `site_search` tool with query parameter set to `test`.

**Expectation:** The tool runs without errors and returns search results with previews.

### Step 2: Verify the Output

Verify that the output contains page information with preview text separated by `---`.

**Expectation:** The output is a string containing page data (page_id, page_title, page_url, preview) separated by `---` for each result.
