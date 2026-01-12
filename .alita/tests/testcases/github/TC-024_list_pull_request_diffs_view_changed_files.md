# list_pull_request_diffs: view changed files

## Priority

Critical

## Objective

Verify PR file diffs are returned with expected fields.

## Test Data Configuration

### GitHub Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Toolkit** | `github` | Toolkit under `alita_sdk/tools` |
| **Tool** | `list_pull_request_diffs` | Exact Python tool name |
| **Primary Input(s)** | `14, ProjectAlita/elitea-testing` | PR number and optional repo |
| **Expected Result** | `{{EXPECTED_DIFF_FILES}}` | Each item includes `path`, `patch`, `status`, `additions`, `deletions`, `changes` |

## Config

path: .alita\tool_configs\git-config.json
generateTestData: false

## Pre-requisites

- Target PR has file changes

## Test Steps & Expectations

### Step 1: Execute the Tool

Run `list_pull_request_diffs` for `14`.

**Expectation:** returns a list.

### Step 2: Verify Core Output Contract

Ensure each element has keys: `path`, `patch`, `status`, `additions`, `deletions`, `changes`.