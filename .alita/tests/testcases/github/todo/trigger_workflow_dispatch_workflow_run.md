# trigger_workflow: dispatch workflow run

## Priority

Critical

## Objective

Trigger a workflow by id or filename and verify return details or deterministic not-found message.

## Test Data Configuration

### GitHub Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Toolkit** | `github` | Toolkit under `alita_sdk/tools` |
| **Tool** | `trigger_workflow` | Exact Python tool name |
| **Primary Input(s)** | `{{WORKFLOW_ID}}, {{REF}}, {{INPUTS}}` | Workflow identifier, ref, inputs |
| **Expected Result** | `{{EXPECTED_RESULT_OR_ERROR}}` | Either success dict with `workflow_id`, `workflow_name`, `workflow_url`, or not-found message string |

## Config

path: .alita\tool_configs\git-config.json
generateTestData: true

## Pre-requisites

- Provide valid repo/workflow or use id to test not-found path

## Test Steps & Expectations

### Step 1: Execute the Tool

Run `trigger_workflow`.

**Expectation:** returns result.

### Step 2: Verify Core Output Contract

Validate presence of success keys or exact not-found string pattern.