# list_files_in_main_branch: Overview repository files on base branch

## Priority

Critical

## Objective

Verify that the `list_files_in_main_branch` tool lists files from the base branch and returns a stable list of paths.

## Test Data Configuration

### GitHub Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Toolkit** | `github` | Toolkit under `alita_sdk/tools` |
| **Tool** | `list_files_in_main_branch` | Exact Python tool name |
| **Primary Input(s)** | `ProjectAlita/elitea-testing` | Optional explicit repo name |
| **Expected Result** | `toolkit-tests/ado-boards/Scenario_8_Link_Work_Items_To_Wiki_Page.feature` | Returned list contains a known path |

## Config

path: .alita\tool_configs\git-config.json
generateTestData: false

## Pre-requisites

- Valid configuration for toolkit `github`
- Environment provides `GITHUB_REPOSITORY`, `GITHUB_ACCESS_TOKEN`, `GITHUB_BASE_BRANCH`
- Known file path `toolkit-tests/ado-boards/Scenario_8_Link_Work_Items_To_Wiki_Page.feature` exists on base branch

## Test Steps & Expectations

### Step 1: Execute the Tool

Execute the `list_files_in_main_branch` tool.
- `repo_name`: `ProjectAlita/elitea-testing`

**Expectation:** The tool returns a list of file paths.

### Step 2: Verify Core Output Contract

Inspect the output list.

**Expectation:** The list includes `toolkit-tests/ado-boards/Scenario_8_Link_Work_Items_To_Wiki_Page.feature` indicating base branch inventory is correctly returned.