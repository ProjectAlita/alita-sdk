# generic_github_api_call: call supported method

## Priority

Critical

## Objective

Call `get_repo` without explicit `full_name_or_id` and verify fallback behavior.

## Test Data Configuration

### GitHub Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Toolkit** | `github` | Toolkit under `alita_sdk/tools` |
| **Tool** | `generic_github_api_call` | Exact Python tool name |
| **Primary Input(s)** | `method='get_repo'` | Method name only |
| **Expected Result** | Dict containing repository metadata including the fields listed below | Either raw data or message that `'raw_data' attribute is missing` |

## Config

path: .alita\tool_configs\git-config.json
generateTestData: false

## Pre-requisites

- Repository env var configured

## Test Steps & Expectations

### Step 1: Execute the Tool

Run `generic_github_api_call` with `method='get_repo'`.

**Expectation:** returns string or dict.

### Step 2: Verify Core Output Contract

Verify that the returned dict (or raw data) contains at least the following repository fields:

- `id`
- `node_id`
- `name`
- `full_name`
- `private`
- `owner` object containing:
	- `login`
	- `id`

The test should pass if these fields are present in the response (or the response contains the expected fallback message about missing `raw_data`).