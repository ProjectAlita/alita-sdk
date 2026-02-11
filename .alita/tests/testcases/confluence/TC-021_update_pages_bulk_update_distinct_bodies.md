# update_pages: Bulk update pages with distinct bodies

## Priority

Critical

## Objective

Ensure bulk update with multiple page IDs and distinct contents returns aggregated success statuses.

## Test Data Configuration

### Confluence Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Toolkit** | `confluence` | Toolkit under `alita_sdk/tools` |
| **Tool** | `update_pages` | Exact Python tool name |
| **Primary Input(s)** | `TC_021_PAGE_IDS_TO_UPDATE`, `TC_021_NEW_CONTENTS_TO_INSERT` | Inputs derived from args_schema |

## Config

path: .alita/tool_configs/confluence-config.json
generateTestData: true

## Pre-requisites

- Valid toolkit config for `confluence`
- Required credentials available via env vars referenced by config
- Create pages with `{{TC_021_PAGE_IDS_TO_UPDATE}}` before test execution
- `{{TC_021_NEW_CONTENTS_TO_INSERT}}` length equals `{{TC_021_PAGE_IDS_TO_UPDATE}}` length

## Test Steps & Expectations

### Step 1: Execute the Tool

Execute `update_pages` with `page_ids={{TC_021_PAGE_IDS_TO_UPDATE}}`, `new_contents={{TC_021_NEW_CONTENTS_TO_INSERT}}`.

**Expectation:** runs without errors and returns output.

### Step 2: Verify Core Output Contract

Validate returned string represents a list where each per-page status contains "was updated successfully".

### Step 3: Verify Individual Page Updates

Execute the `read_page_by_id` tool for each page from `{{TC_021_PAGE_IDS_TO_UPDATE}}`.
If id's are ints convert them to strings.
If the pages are returned with retries, that should be considered as success.
Verify that the output contains the updated page content as text.

### Step 4: Delete created pages

Execute `delete_page` for each page from `{{TC_021_PAGE_IDS_TO_UPDATE}}`.
If id's are ints convert them to strings.
If the pages are deleted with retries, that should be considered as success

**Expectation:** returns confirmation that the pages have been successfully deleted.