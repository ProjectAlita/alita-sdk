# update_page_by_title: Update body and labels by title

## Priority

Critical

## Objective

Ensure updating content and labels using page title returns a success message via title resolution.

## Test Data Configuration

### Confluence Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Toolkit** | `confluence` | Toolkit under `alita_sdk/tools` |
| **Tool** | `update_page_by_title` | Exact Python tool name |
| **Primary Input(s)** | `{{PAGE_TITLE_OF_PAGE_TO_UPDATE}}, {{NEW_BODY_OF_THE_PAGE}}, {{NEW_LABEL}}` | Required and optional inputs derived from args_schema |

## Config

path: .alita/tool_configs/confluence-config.json
generateTestData: true

## Pre-requisites

- Valid toolkit config for `confluence`
- Required credentials available via env vars referenced by config
- Target page with `{{PAGE_TITLE_OF_PAGE_TO_UPDATE}}` exists and is accessible

## Test Steps & Expectations

### Step 1: Execute the Tool

Execute `update_page_by_title` with `page_title={{PAGE_TITLE_OF_PAGE_TO_UPDATE}}`, `new_body={{NEW_BODY_OF_THE_PAGE}}`, `new_labels={{NEW_LABEL}}`, `representation=storage`.

**Expectation:** runs without errors and returns output.

### Step 2: Verify Core Output Contract

Validate output contains "was updated successfully" and includes a web UI link. If title is not found, tool returns "Page with title ... not found." (not expected in this scenario).

### Step 3: Delete created pages

Execute `delete_page` with title `{{PAGE_TITLE_OF_PAGE_TO_UPDATE}}`.

**Expectation:** returns confirmation that the pages have been successfully deleted.