# Execute Generic Confluence

## Objective

Verify that the `execute_generic_confluence` tool correctly executes generic Confluence REST API calls with specified method, URL, and parameters.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Space** | `AT` | Target Confluence space key |
| **Base URL** | `https://epamelitea.atlassian.net/` | Confluence instance URL |
| **Tool** | `execute_generic_confluence` | Confluence tool to execute generic API calls |
| **Method** | `GET` | HTTP method to use |
| **Relative URL** | `/rest/api/space/AT` | Relative API path |

## Config

path: .alita\tool_configs\confluence-config.json
generateTestData: false

## Pre-requisites

- A Confluence space `AT` exists and is accessible
- Valid Confluence API token with appropriate permissions
- Network access to Confluence REST API

## Test Steps & Expectations

### Step 1: Execute the Tool

Execute the `execute_generic_confluence` tool with method `GET` and relative_url `/rest/api/space/AT`.

**Expectation:** The tool runs without errors and returns API response.

### Step 2: Verify the Output

Verify that the output contains HTTP response information including status code and response text.

**Expectation:** The output is a string formatted as `HTTP: {method}{url} -> {status_code}{reason}{response_text}` with successful status code (200).
