# Execute Generic Confluence

## Objective

Verify that the `execute_generic_confluence` tool correctly executes generic Confluence REST API calls with specified method, URL, and parameters.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Space** | `MFS` | Target Confluence space key |
| **Cloud** | `true` | Using Confluence Cloud instance |
| **Username** | `variushkin@gmail.com` | Confluence user email |
| **API Key** | `CONFLUENCE_API_KEY` | Confluence API token for authentication |
| **Base URL** | `https://variushkin.atlassian.net` | Confluence instance URL |
| **Tool** | `execute_generic_confluence` | Confluence tool to execute generic API calls |
| **Method** | `GET` | HTTP method to use |
| **Relative URL** | `/rest/api/space/MFS` | Relative API path |

## Config

path: .github\ai_native\testcases\confluence\configs\confluence-config.json

## Pre-requisites

- A Confluence space `MFS` exists and is accessible
- Valid Confluence API token with appropriate permissions
- Network access to Confluence REST API

## Test Steps & Expectations

### Step 1: Execute the Tool

Execute the `execute_generic_confluence` tool with method `GET` and relative_url `/rest/api/space/MFS`.

**Expectation:** The tool runs without errors and returns API response.

### Step 2: Verify the Output

Verify that the output contains HTTP response information including status code and response text.

**Expectation:** The output is a string formatted as `HTTP: {method}{url} -> {status_code}{reason}{response_text}` with successful status code (200).
