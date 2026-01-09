# Get Page with Image Descriptions

## Objective

Verify that the `get_page_with_image_descriptions` tool correctly retrieves a Confluence page and replaces images with LLM-generated textual descriptions.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Space** | `AT` | Target Confluence space key |
| **Base URL** | `https://epamelitea.atlassian.net/` | Confluence instance URL |
| **Tool** | `get_page_with_image_descriptions` | Confluence tool to execute for getting page with image descriptions |
| **Page ID** | `104300545` | ID of the page containing images |

## Config

path: .alita\tool_configs\confluence-config.json
generateTestData: false

## Pre-requisites

- A Confluence space `AT` exists and is accessible
- Valid Confluence API token with read permissions
- A page with ID `104300545` exists and contains at least one image
- LLM is configured and available for image analysis

## Test Steps & Expectations

### Step 1: Execute the Tool

Execute the `get_page_with_image_descriptions` tool with page_id parameter set to `104300545`.

**Expectation:** The tool runs without errors and returns page content with images replaced by descriptions.

### Step 2: Verify the Output

Verify that the output contains page content in markdown format with image descriptions instead of image references.

**Expectation:** The output is a string containing the actual immage describes field with green crops. Make sure that the description matches contextually.  
