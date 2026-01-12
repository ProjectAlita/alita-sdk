# Get Page Attachments

## Objective

Verify that the `get_page_attachments` tool correctly retrieves all attachments from a Confluence page including metadata, comments, content, and LLM analysis.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Space** | `AT` | Target Confluence space key |
| **Base URL** | `https://epamelitea.atlassian.net/` | Confluence instance URL |
| **Tool** | `get_page_attachments` | Confluence tool to execute for retrieving attachments |
| **Page ID** | `140869772` | ID of the page with attachments |

## Config

path: .alita\tool_configs\confluence-config.json
generateTestData: false

## Pre-requisites

- A Confluence space `AT` exists and is accessible
- Valid Confluence API token with read permissions
- A page with ID `140869772` exists and has at least one attachment
- If attachement is not present, add one

## Test Steps & Expectations

### Step 1: Execute the Tool

Execute the `get_page_attachments` tool with page_id parameter set to `140869772`.

**Expectation:** The tool runs without errors and returns attachment information.

### Step 2: Verify the Output

Verify that the output contains a list of attachment dictionaries with metadata, comments, content, and llm_analysis keys.

**Expectation:** The output is a list of dictionaries, and contains 
- metadata:
  - name: test_attachment.txt
  - size: 25
  - creator: Vladyslav Variushkin