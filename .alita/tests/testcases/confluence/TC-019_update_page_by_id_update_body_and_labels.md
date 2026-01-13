# update_page_by_id: Update body and labels on existing page

## Priority

Critical

## Objective

Ensure updating page content and labels by page ID returns a success message and preserves core output contract.

## Test Data Configuration

### Confluence Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Toolkit** | `confluence` | Toolkit under `alita_sdk/tools` |
| **Tool** | `update_page_by_id` | Exact Python tool name |
| **Primary Input(s)** | `TC_019_PAGE_ID_TO_UPDATE`, `TC_019_NEW_BODY`, `TC_019_NEW_LABEL` | Required and optional inputs derived from args_schema |

## Config

path: .alita/tool_configs/confluence-config.json
generateTestData: true

## Pre-requisites

- Valid toolkit config for `confluence`
- Create page with `{{TC_019_PAGE_ID_TO_UPDATE}}` before test execution
- `{{TC_019_NEW_BODY}}` is valid per representation `storage`

## Test Steps & Expectations

### Step 1: Execute the Tool

Execute `update_page_by_id` with `page_id={{TC_019_PAGE_ID_TO_UPDATE}}`, `new_body={{TC_019_NEW_BODY}}`, `new_labels={{TC_019_NEW_LABEL}}`, `representation=storage`.

**Expectation:** runs without errors and returns output.

### Step 2: Verify Core Output Contract

Validate output string contains "was updated successfully" and the passed `{{TC_019_PAGE_ID_TO_UPDATE}}`. When labels provided, details include `labels` list.

### Step 3: Execute the Tool

Execute the `read_page_by_id` tool with page_id parameter set to `{{TC_019_PAGE_ID_TO_UPDATE}}`.
Verify that the output contains the updated page content as text.

### Step 4: Delete created pages

Execute `delete_page` for each page from `{{TC_019_PAGE_ID_TO_UPDATE}}`.

**Expectation:** returns confirmation that the pages have been successfully deleted.
