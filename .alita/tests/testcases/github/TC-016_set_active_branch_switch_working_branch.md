# set_active_branch: Switch working branch for subsequent operations

## Priority

Critical

## Objective

Verify that `set_active_branch` updates the wrapper's active branch when the branch exists.

## Test Data Configuration

### GitHub Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Toolkit** | `github` | Toolkit under `alita_sdk/tools` |
| **Tool** | `set_active_branch` | Exact Python tool name |
| **Primary Input(s)** | `{{BRANCH_NAME}}` | Existing branch name to set active |
| **Expected Result** | `{{EXPECTED_BRANCH_NAME}}` | Success message references branch name |

## Config

path: .alita\tool_configs\git-config.json
generateTestData: false

## Pre-requisites

- Valid configuration for toolkit `github`
- Environment provides `GITHUB_REPOSITORY`, `GITHUB_ACCESS_TOKEN`
- Branch `switch_branch_tc` exists in the default repository

## Test Steps & Expectations

### Step 1: Execute the Tool

Execute the `set_active_branch` tool with:
- `branch_name`: `switch_branch_tc`

**Expectation:** The tool runs without errors and returns a success message.

### Step 2: Verify Core Output Contract

Inspect the output string.

**Expectation:** The output equals or contains `Active branch set to 'switch_branch_tc`. If branch missing, message explicitly states "not found".

### Step 3: Check if file is present in the new active branch

Execute the `read_file` tool from GitHub with file path `switch_branch.txt` using branch `switch_branch_tc`.

Inspect the output string.

**Expectation:** The output equals or contains `BRANCH IS SWITCHED`.