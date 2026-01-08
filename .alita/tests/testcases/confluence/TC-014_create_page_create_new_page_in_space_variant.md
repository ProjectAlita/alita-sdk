# create_page: Create a new page with markdown body variant

## Priority

High

## Objective

Validate that create_page succeeds when representation is `wiki` (markdown). The contract must still include title, id, space key, author, link in the message.

## Test Data Configuration

### Confluence Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Toolkit** | `confluence` | Toolkit under `alita_sdk/tools` |
| **Tool** | `create_page` | Exact Python tool name |
| **Primary Input(s)** | `{{SPACE}}=AT`, `{{PAGE_TITLE}}=AI Test page {{RANDOM_STRING}}`, `{{PAGE_BODY_MD}}`, `{{STATUS}}=current`, `{{REPRESENTATION}}=wiki`, `{{LABEL}}=automation` | Inputs derived from args_schema: space, title, body, status, parent_id, representation, label |

## Config

path: .alita/tool_configs/confluence-config.json
generateTestData: true

## Pre-requisites

- Valid toolkit config for `confluence`
- Space `{{SPACE}}` exists and is accessible
- Title `{{PAGE_TITLE}}` does not already exist in the space and not need to create one if does not exist
- If `{{PARENT_ID}}` is not provided, space homepage must be retrievable

## Test Steps & Expectations

### Step 1: Execute the Tool

Execute `create_page` with:
- space=`{{SPACE}}`
- title=`{{PAGE_TITLE}}`
- body=`{{PAGE_BODY_MD}}` (markdown)
- status=`current`
- representation=`wiki`

**Expectation:** runs without errors and returns a success string.

### Step 2: Verify Core Output Contract

Validate returned text includes:
- "The page '{{PAGE_TITLE}}' was created under the parent page"
- Details object with keys: title, id, space key, author, link

### Step 3: Delete created page

Execute `delete_page` with only `page_title` set: `{{PAGE_TITLE}}`.

**Expectation:** returns confirmation that the page has been successfully deleted.