# get_issues: list repository issues

## Priority

Critical

## Objective

List issues and verify each has basic fields.

## Test Data Configuration

### GitHub Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Toolkit** | `github` | Toolkit under `alita_sdk/tools` |
| **Tool** | `get_issues` | Exact Python tool name |
| **Primary Input(s)** | `N/A` | No inputs required |
| **Expected Result** | `{{EXPECTED_ISSUE_FIELDS}}` | Each issue has `number`, `title`, `state`, `url` |

## Config

path: .alita\tool_configs\git-config.json
generateTestData: false

## Pre-requisites

- Repository has issues

## Test Steps & Expectations

### Step 1: Execute the Tool

Run `get_issues`.

**Expectation:** returns list of issues.

### Step 2: Verify Core Output Contract

Check each item includes `number`, `title`, `state`, `url`.
Check at least one issue is present with title matching `AI Automation issue`.