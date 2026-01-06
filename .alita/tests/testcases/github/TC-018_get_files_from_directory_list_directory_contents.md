# get_files_from_directory: List directory contents recursively

## Priority

High

## Objective

Validate that `get_files_from_directory` returns all file paths under a given directory on the active branch.

## Test Data Configuration

### GitHub Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Toolkit** | `github` | Toolkit under `alita_sdk/tools` |
| **Tool** | `get_files_from_directory` | Exact Python tool name |
| **Primary Input(s)** | `ui-tests`, `ProjectAlita/elitea-testing` | Target directory path and optional repo name |
| **Expected Result** | `components, README.md` | Returned list includes a known child file path |

## Config

path: .alita\tool_configs\git-config.json
generateTestData: false

## Pre-requisites

- Valid configuration for toolkit `github`
- Directory `ui-tests` exists on active branch and contains files

## Test Steps & Expectations

### Step 1: Execute the Tool

Execute the `get_files_from_directory` tool with:
- `directory_path`: `ui-tests`
- `repo_name`: `ProjectAlita/elitea-testing` (optional)

**Expectation:** The tool returns a list of file paths.

### Step 2: Verify Core Output Contract

Inspect the output list.

**Expectation:** The list includes `components, README.md` confirming recursive traversal results.