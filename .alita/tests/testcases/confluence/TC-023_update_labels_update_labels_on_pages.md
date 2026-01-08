# update_labels: Update labels on pages by IDs

## Priority

Critical

## Objective

Ensure updating labels for multiple pages returns aggregated success statuses and applies default labels.

## Test Data Configuration

### Confluence Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Toolkit** | `confluence` | Toolkit under `alita_sdk/tools` |
| **Tool** | `update_labels` | Exact Python tool name |
| **Primary Input(s)** | `{{PAGE_IDS_TO_UPDATE_LABELS}}, {{NEW_LABELS}}` | Inputs derived from args_schema |
| **Expected Result** | `{{EXPECTED_STATUS_LIST_SNIPPET}}` | Stringified list where each entry contains "was updated successfully" |

## Config

path: .alita/tool_configs/confluence-config.json
generateTestData: true

## Pre-requisites

- Valid toolkit config for `confluence`
- Required credentials available via env vars referenced by config
- Target pages with `{{PAGE_IDS_TO_UPDATE_LABELS}}` exist and are accessible
- `{{NEW_LABELS}}` is a list of label strings

## Test Steps & Expectations

### Step 1: Execute the Tool

Execute `update_labels` with `page_ids={{PAGE_IDS_TO_UPDATE_LABELS}}`, `new_labels={{NEW_LABELS}}`.

**Expectation:** runs without errors and returns output.

### Step 2: Verify Core Output Contract

Validate returned string represents a list where each per-page status contains "was updated successfully".

### Step 3: Verify Individual Page Updates

Execute the `list_pages_with_label` tool for any label from `{{NEW_LABELS}}`.
Verify that the output contains pages `{{PAGE_IDS_TO_UPDATE_LABELS}}`.

### Step 4: Delete created pages

Execute `delete_page` for each page from `{{PAGE_IDS_TO_UPDATE_LABELS}}`.

**Expectation:** returns confirmation that the pages have been successfully deleted.