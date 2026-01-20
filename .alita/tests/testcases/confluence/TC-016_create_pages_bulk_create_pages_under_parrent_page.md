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
| **Primary Input(s)** | `{{SPACE}}=AT`, `{{TC_16_PAGES_INFO_JSON}}`, `{{STATUS}}=current`. `{{TC_16_PARENT_ID}}` | Inputs derived from args_schema: space, pages_info, status, parent_id |

## Config

path: .alita/tool_configs/confluence-config.json
generateTestData: true

## Pre-requisites

- Valid toolkit config for `confluence`
- Confluence credentials via env vars
- Space `{{SPACE}}` exists and accessible
- Create page with ID `{{TC_16_PARENT_ID}}` to serve as parent
- All titles are unique in the space

## Test Steps & Expectations

### Step 1: Execute the Tool

Execute `create_pages` with:
- space=`{{SPACE}}`
- pages_info=`{{TC_16_PAGES_INFO_JSON}}` (e.g., `[{"Page A": "<h1>A</h1>"}, {"Page B": "<p>B</p>"}]`)
- status=`current`
- parent_id=`{{TC_16_PARENT_ID}}`

**Expectation:** runs without errors and returns a list string of confirmations.

### Step 2: Verify Core Output Contract

For each created page message, validate it includes:
- "The page '<title>' was created under the parent page"
- Details keys: title, id, space key, author, link

### Step 3: Delete created pages

Execute `delete_page` for each page from `{{TC_16_PAGES_INFO_JSON}}`.
If id's are ints convert them to strings.
If the pages are deleted with retries, that should be considered as success

**Expectation:** returns confirmation that the pages have been successfully deleted.