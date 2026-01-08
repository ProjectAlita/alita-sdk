# create_page: Create a new page in Confluence space

## Priority

Critical

## Objective

Validate that create_page publishes a new page with HTML body in the specified space and returns deterministic details (title, id, space key, author, link). Ensure label assignment and default labels flow.

## Test Data Configuration

### Confluence Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Toolkit** | `confluence` | Toolkit under `alita_sdk/tools` |
| **Tool** | `create_page` | Exact Python tool name |
| **Primary Input(s)** | `{{SPACE}}=AT`, `{{PAGE_TITLE}}=AI Test page {{RANDOM_STRING}}`, `{{PAGE_BODY_TEXT}}={{RANDOM_STRING}}`, `{{STATUS}}=current`, `{{REPRESENTATION}}=storage`, `{{LABEL}}=automation` | Inputs derived from args_schema: space, title, body, status, parent_id, representation, label |

## Config

path: .alita/tool_configs/confluence-config.json
generateTestData: true

## Pre-requisites

- Valid toolkit config for `confluence`
- Space `{{SPACE}}` exists and is accessible
- Title `{{PAGE_TITLE}}` does not already exist in the space. Do not create any pages beforehand.

## Test Steps & Expectations

### Step 1: Execute the Tool

Execute `create_page` with:
- space=`{{SPACE}}`
- title=`{{PAGE_TITLE}}`
- body=`{{PAGE_BODY_TEXT}}`
- status=`{{STATUS}}`
- representation=`{{REPRESENTATION}}`
- label=`{{LABEL}}`

**Expectation:** runs without errors and returns a success string.

### Step 2: Verify Core Output Contract

Validate returned text includes:
- "The page '{{PAGE_TITLE}}' was created under the parent page"
- "Details: {'title': ..., 'id': ..., 'space key': ..., 'author': ..., 'link': ...}"
- If label provided, ensure label name is present in details.

### Step 3: Delete created page

Execute `delete_page` with only `page_title` set: `{{PAGE_TITLE}}`.

**Expectation:** returns confirmation that the page has been successfully deleted.