# get_workflow_status: check run status

## Priority

Critical

## Objective

Retrieve workflow run status and validate keys or error dict.

## Test Data Configuration

### GitHub Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Toolkit** | `github` | Toolkit under `alita_sdk/tools` |
| **Tool** | `get_workflow_status` | Exact Python tool name |
| **Primary Input(s)** | `{{RUN_ID}}` | Workflow run ID |
| **Expected Result** | `{{EXPECTED_STATUS_DICT}}` | Dict with `id`, `name`, `status`, `conclusion`, `jobs` and `url` or `error:true` with `message` |

## Config

path: .alita\tool_configs\git-config.json
generateTestData: true

## Pre-requisites

- Run exists or expect error path

## Test Steps & Expectations

### Step 1: Execute the Tool

Run `get_workflow_status`.

**Expectation:** returns dict.

### Step 2: Verify Core Output Contract

Validate keys for success or `error:true` structure.