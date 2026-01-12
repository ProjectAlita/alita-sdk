# list_project_issues: list board items

## Priority

Critical

## Objective

List issues in a project and validate returned structure keys.

## Test Data Configuration

### GitHub Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Toolkit** | `github` | Toolkit under `alita_sdk/tools` |
| **Tool** | `list_project_issues` | Exact Python tool name |
| **Primary Input(s)** | `{{BOARD_REPO}}=ProjectAlita/elitea-testing, {{PROJECT_NUMBER}}=11, {{ITEMS_COUNT}}=2` | Board repo, project number, item count |

## Config

path: .alita\tool_configs\git-config.json
generateTestData: false

## Pre-requisites

- Project exists

## Test Steps & Expectations

### Step 1: Execute the Tool

Run `list_project_issues` with the following arguments 
 - Board Repo ProjectAlita/elitea-testing
 - Project Number 11
 - Items Count 2

**Expectation:** returns dict.

### Step 2: Verify Core Output Contract

Confirm response matches Expected Output Example structure (values/IDs may differ run-to-run):
- Top-level keys `id`, `title`, `url`, `fields`, `items` present with correct types.
- `fields` contains 10 entries including a `Status` field with single-select options (should include Todo / In Progress / Done).
- `items` is an array with length `{{ITEMS_COUNT}}`; each entry has `id`, `type`, `content` (issue id/number/title/url/state/labels/assignees), and `fieldValues` reflecting Title and Status.