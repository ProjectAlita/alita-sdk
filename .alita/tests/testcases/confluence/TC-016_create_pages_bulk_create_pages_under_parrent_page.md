# create_pages: Bulk create pages with mixed representations

## Priority

High

## Objective

Validate that create_pages works when underlying create_page handles different representations per item. Use a JSON that mixes HTML and markdown bodies. Contract remains list of success messages.

## Test Data Configuration

### Confluence Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Toolkit** | `confluence` | Toolkit under `alita_sdk/tools` |
| **Tool** | `create_pages` | Exact Python tool name |
| **Primary Input(s)** | `{{SPACE}}=AT`, `{{PAGES_INFO_JSON_VARIANT}}`, `{{STATUS}}=current`. `{{PARENT_ID}}` | Inputs derived from args_schema: space, pages_info, status, parent_id |

## Config

path: .alita/tool_configs/confluence-config.json
generateTestData: true

## Pre-requisites

- Valid toolkit config for `confluence`
- Confluence credentials via env vars
- Space `{{SPACE}}` exists and accessible
- All titles are unique in the space

## Test Steps & Expectations

### Step 1: Execute the Tool

Execute `create_pages` with:
- space=`{{SPACE}}`
- pages_info=`{{PAGES_INFO_JSON_VARIANT}}` (e.g., `[{"Page A": "<h1>A</h1>"}, {"Page B": "<p>B</p>"}]`)
- status=`current`
- parent_id=`{{PARENT_ID}}`

**Expectation:** runs without errors and returns a list string of confirmations.

### Step 2: Verify Core Output Contract

For each created page message, validate it includes:
- "The page '<title>' was created under the parent page"
- Details keys: title, id, space key, author, link

### Step 3: Delete created pages

Execute `delete_page` for each page from `{{PAGES_INFO_JSON_VARIANT}}`.

**Expectation:** returns confirmation that the pages have been successfully deleted.