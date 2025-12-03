# Read Page by ID

## Objective

Verify that the `read_page_by_id` tool correctly retrieves the content of a Confluence page using its page ID.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Space** | `MFS` | Target Confluence space key |
| **Cloud** | `true` | Using Confluence Cloud instance |
| **Username** | `variushkin@gmail.com` | Confluence user email |
| **API Key** | `CONFLUENCE_API_KEY` | Confluence API token for authentication |
| **Base URL** | `https://variushkin.atlassian.net` | Confluence instance URL |
| **Tool** | `read_page_by_id` | Confluence tool to execute for reading page content |
| **Page ID** | `262313` | ID of the page to read |

## Config

path: .github\ai_native\testcases\confluence\configs\confluence-config.json

## Pre-requisites

- A Confluence space `MFS` exists and is accessible
- Valid Confluence API token with read permissions
- A page with ID `262313` exists and is accessible

## Test Steps & Expectations

### Step 1: Execute the Tool

Execute the `read_page_by_id` tool with page_id parameter set to `262313`.

**Expectation:** The tool runs without errors and returns page content.

### Step 2: Verify the Output

Verify that the output contains the page content as text.

**Expectation:** The output is a string containing the page content in markdown or text format.
