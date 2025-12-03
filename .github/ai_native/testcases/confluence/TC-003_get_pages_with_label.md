# Get Pages with Label

## Objective

Verify that the `get_pages_with_label` tool correctly retrieves pages tagged with a specific label in the Confluence space.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Space** | `MFS` | Target Confluence space key |
| **Cloud** | `true` | Using Confluence Cloud instance |
| **Username** | `variushkin@gmail.com` | Confluence user email |
| **API Key** | `CONFLUENCE_API_KEY` | Confluence API token for authentication |
| **Base URL** | `https://variushkin.atlassian.net` | Confluence instance URL |
| **Tool** | `get_pages_with_label` | Confluence tool to execute for retrieving labeled pages |
| **Label** | `test-label` | Label to filter pages |

## Config

path: .github\ai_native\testcases\confluence\configs\confluence-config.json

## Pre-requisites

- A Confluence space `MFS` exists and is accessible
- Valid Confluence API token with read permissions
- At least one page exists with the label `test-label`

## Test Steps & Expectations

### Step 1: Execute the Tool

Execute the `get_pages_with_label` tool with the label parameter set to `test-label`.

**Expectation:** The tool runs without errors and returns page information.

### Step 2: Verify the Output

Verify that the output contains page details including page_id, page_title, page_url, and content.

**Expectation:** The output is a list containing at least one page with the specified label, formatted as a string with page details.
