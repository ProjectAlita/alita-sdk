# Get Page Attachments

## Objective

Verify that the `get_page_attachments` tool correctly retrieves all attachments from a Confluence page including metadata, comments, content, and LLM analysis.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Space** | `MFS` | Target Confluence space key |
| **Cloud** | `true` | Using Confluence Cloud instance |
| **Username** | `variushkin@gmail.com` | Confluence user email |
| **API Key** | `CONFLUENCE_API_KEY` | Confluence API token for authentication |
| **Base URL** | `https://variushkin.atlassian.net` | Confluence instance URL |
| **Tool** | `get_page_attachments` | Confluence tool to execute for retrieving attachments |
| **Page ID** | `262313` | ID of the page with attachments |

## Config

path: .github\ai_native\testcases\confluence\configs\confluence-config.json

## Pre-requisites

- A Confluence space `MFS` exists and is accessible
- Valid Confluence API token with read permissions
- A page with ID `262313` exists and has at least one attachment

## Test Steps & Expectations

### Step 1: Execute the Tool

Execute the `get_page_attachments` tool with page_id parameter set to `262313`.

**Expectation:** The tool runs without errors and returns attachment information.

### Step 2: Verify the Output

Verify that the output contains a list of attachment dictionaries with metadata, comments, content, and llm_analysis keys.

**Expectation:** The output is a list of dictionaries, each containing attachment metadata (id, title, mediaType, fileSize, creator, created, updated), comments, content (truncated to max_content_length), and llm_analysis for supported file types.
