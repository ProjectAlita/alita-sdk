# list_files_in_bot_branch: Overview files in active working branch

## Priority

High

## Objective

Validate that `list_files_in_bot_branch` returns file paths from the current active branch and handles branch variation reliably.

## Test Data Configuration

### GitHub Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Toolkit** | `github` | Toolkit under `alita_sdk/tools` |
| **Tool** | `list_files_in_bot_branch` | Exact Python tool name |
| **Primary Input(s)** | `ProjectAlita/elitea-testing` | Optional explicit repo name |
| **Expected Result** | `api-tests/README.md` | Returned list contains a known path present on active branch |

## Config

path: .alita\tool_configs\git-config.json
generateTestData: false

## Pre-requisites

- Valid configuration for toolkit `github`
- Environment provides `GITHUB_REPOSITORY`, `GITHUB_ACCESS_TOKEN`, `ACTIVE_BRANCH`
- Active branch is set and contains `api-tests/README.md`

## Test Steps & Expectations

### Step 1: Execute the Tool

Execute the `list_files_in_bot_branch` tool.
- `repo_name`: `ProjectAlita/elitea-testing`

**Expectation:** The tool returns a list of file paths.

### Step 2: Verify Core Output Contract

Inspect the output list.

**Expectation:** The list includes `api-tests/README.md` confirming correct enumeration of active branch files.