# create_pages: Bulk create pages from JSON list

## Priority

Critical

## Objective

Validate that create_pages creates multiple pages from JSON `pages_info` under resolved parent_id (space homepage when not provided) and returns a stringified list of per-page success messages.

## Test Data Configuration

### Confluence Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Toolkit** | `confluence` | Toolkit under `alita_sdk/tools` |
| **Tool** | `create_pages` | Exact Python tool name |
| **Primary Input(s)** | `{{SPACE}}=AT`, `{{PAGES_INFO_JSON}}`, `{{STATUS}}=current` | Inputs derived from args_schema: space, pages_info, status, parent_id |

## Config

path: .alita/tool_configs/confluence-config.json
generateTestData: true
0
## Pre-requisites

- Valid toolkit config for `confluence`
- Confluence credentials via env vars
- Space `{{SPACE}}` exists and accessible
- All titles inside `{{PAGES_INFO_JSON}}` are unique and does not contain more than 2 pages

## Test Steps & Expectations

### Step 1: Execute the Tool

Execute `create_pages` with:
- space=`{{SPACE}}`
- pages_info=`{{PAGES_INFO_JSON}}` (e.g., `[{"Page A": "<h1>A</h1>"}, {"Page B": "<p>B</p>"}]`)
- status=`current`

**Expectation:** runs without errors and returns a stringified list with per-page confirmations.

### Step 2: Verify Core Output Contract

For each created page message, validate it includes:
- Details keys: title, id, space key, author, link

### Step 3: Delete created pages

Execute `delete_page` for each page from `{{PAGES_INFO_JSON}}`.

**Expectation:** returns confirmation that the pages have been successfully deleted.