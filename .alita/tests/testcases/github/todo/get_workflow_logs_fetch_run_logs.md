# get_workflow_logs: fetch run logs

## Priority

Critical

## Objective

Retrieve logs for a workflow run and validate core fields or fallback job details.

## Test Data Configuration

### GitHub Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Toolkit** | `github` | Toolkit under `alita_sdk/tools` |
| **Tool** | `get_workflow_logs` | Exact Python tool name |
| **Primary Input(s)** | `{{RUN_ID}}` | Workflow run ID |
| **Expected Result** | `{{EXPECTED_LOGS_RESULT}}` | Dict with `run_id`, `status`, `conclusion`, `logs` map or `job_details` with `note` |

## Config

path: .alita\tool_configs\git-config.json
generateTestData: true

## Pre-requisites

- Provide run id or test error path

## Test Steps & Expectations

### Step 1: Execute the Tool

Run `get_workflow_logs`.

**Expectation:** returns dict.

### Step 2: Verify Core Output Contract

Validate presence of either `logs` or `job_details` key.