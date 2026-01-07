# list_open_pull_requests: view active PRs

## Priority

Critical

## Objective

Ensure open PRs are listed with core fields present.

## Test Data Configuration

### GitHub Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Toolkit** | `github` | Toolkit under `alita_sdk/tools` |
| **Tool** | `list_open_pull_requests` | Exact Python tool name |
| **Primary Input(s)** | `N/A` | No inputs required |
| **Expected Result** | `{{EXPECTED_PR_FIELDS}}` | Each PR item includes `number`, `title`, `state`, `head`, `base` |

## Config

path: .alita\tool_configs\git-config.json
generateTestData: false

## Pre-requisites

- Valid config and credentials
- At least one open PR or generate test PR

## Test Steps & Expectations

### Step 1: Execute the Tool

Run `list_open_pull_requests`.

**Expectation:** returns an array of PRs.

### Step 2: Verify Core Output Contract

Validate each PR dict contains keys `number`, `title`, `state`, `head`, `base`.