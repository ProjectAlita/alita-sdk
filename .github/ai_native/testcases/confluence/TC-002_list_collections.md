# List Collections

## Objective

Verify that the `list_collections` tool correctly retrieves a list of all collections in the Confluence vector store.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Space** | `AT` | Target Confluence space key |
| **Username** | `CONFLUENCE_USERNAME` | Confluence user email |
| **API Key** | `CONFLUENCE_API_KEY` | Confluence API token for authentication |
| **Base URL** | `https://epamelitea.atlassian.net/` | Confluence instance URL |
| **Tool** | `list_collections` | Confluence tool to execute for retrieving collections list |

## Config

path: .alita\tool_configs\confluence-config.json

## Pre-requisites

- A Confluence space `AT` exists and is accessible
- Valid Confluence API token with appropriate permissions
- At least one collection named `test` exists in the vector store

## Test Steps & Expectations

### Step 1: Execute the Tool

Execute the `list_collections` tool to retrieve all collections from the vector store.

**Expectation:** The tool runs without errors and returns a list of collections.

### Step 2: Verify the Output

Verify that the output contains the expected collection.

**Expectation:** The output is `["test"]`.
