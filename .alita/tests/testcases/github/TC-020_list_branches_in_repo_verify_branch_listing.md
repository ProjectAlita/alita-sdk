# list_branches_in_repo: verify branch listing

## Priority

Critical

## Objective

Ensure branches are listed and include expected branch names.

## Test Data Configuration

### GitHub Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Toolkit** | `github` | Toolkit under `alita_sdk/tools` |
| **Tool** | `list_branches_in_repo` | Exact Python tool name |
| **Primary Input(s)** | `N/A` | No inputs required |
| **Expected Result** | `switch_branch_tc` | Returned list contains known branch names (e.g., `main`) |

## Config

path: .alita\tool_configs\git-config.json
generateTestData: false

## Pre-requisites

- Valid toolkit config for `github`
- `GITHUB_ACCESS_TOKEN` available via env vars referenced by config
- Repository `ProjectAlita/elitea-testing` exists and is accessible

## Test Steps & Expectations

### Step 1: Execute the Tool

Execute `list_branches_in_repo` with no inputs.

**Expectation:** runs without errors and returns output.

### Step 2: Verify Core Output Contract

Validate the output is a list of branch objects where each item includes `name` and `protected`. Confirm `switch_branch_tc` is present.
