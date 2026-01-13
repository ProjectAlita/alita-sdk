# delete_page: Delete page by id or title

## Priority

Critical

## Objective

Validate that delete_page removes a page when either `page_id` or `page_title` is provided, and returns deterministic success or resolution message.

## Test Data Configuration

### Confluence Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Toolkit** | `confluence` | Toolkit under `alita_sdk/tools` |
| **Tool** | `delete_page` | Exact Python tool name |
| **Primary Input(s)** | `TC_017_PAGE_ID` or `TC_017_PAGE_TITLE` | Inputs derived from args_schema: page_id or page_title |

## Config

path: .alita/tool_configs/confluence-config.json
generateTestData: true

## Pre-requisites

- Valid toolkit config for `confluence`
- Confluence credentials via env vars
- Target page exists and is deletable by the current user
- Create page for deletion test with `{{TC_017_PAGE_ID}}` and title `{{TC_017_PAGE_TITLE}}`

## Test Steps & Expectations

### Step 1: Execute the Tool

Execute `delete_page` with only `page_id` set: `{{TC_017_PAGE_ID}}`.

**Expectation:** returns "Page with ID '<resolved_id>' has been successfully deleted."

### Step 2: Verify Core Output Contract

- Ensure message matches success pattern when ID provided.
- If not found, confirm message: "Page instance could not be resolved with id '<id>' and/or title '<title>'".

### Step 3: Verify page is removed by searching title

- Execute a page lookup/search using `read_page_by_id` with `{{TC_017_PAGE_ID}}`.

**Expectation:** the lookup/search MUST indicate the page is not present. Acceptable outcomes include:

- An explicit not-found/resolve message such as: "Page instance could not be resolved with id '<id>' and/or title '<title>'" (where `<id>` may be empty if only title was supplied).
- An empty result set, `null` result, or an HTTP 404 / equivalent toolkit-level error indicating the page does not exist.

If the search returns a page (title or id still resolvable), the test must fail — the delete operation did not remove the page.
