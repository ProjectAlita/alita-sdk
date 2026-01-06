# get_pull_request: fetch PR details

## Priority

Critical

## Objective

Retrieve a PR by number and verify returned details.

## Test Data Configuration

### GitHub Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Toolkit** | `github` | Toolkit under `alita_sdk/tools` |
| **Tool** | `get_pull_request` | Exact Python tool name |
| **Primary Input(s)** | `14, ProjectAlita/elitea-testing` | PR number and optional repo override |
| **Expected Result** | `{{EXPECTED_PR_SUMMARY}}` | Dict includes `title`, `number`, `body`, `pr_url`, `comments`, `commits` |

## Config

path: .alita\tool_configs\git-config.json
generateTestData: false

## Pre-requisites

- PR number exists

## Test Steps & Expectations

### Step 1: Execute the Tool

Run `get_pull_request` with `pr_number=14`.

**Expectation:** returns dict without errors.

### Step 2: Verify Core Output Contract

Validate keys: `title`, `number`, `body`, `pr_url`. `comments` and `commits` are present as arrays or strings.
Title matches `AI Testing pull request`, number is `14`.