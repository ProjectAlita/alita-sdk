# get_commits: list recent commits

## Priority

Critical

## Objective

Retrieve recent commits and validate core fields and count limit.

## Test Data Configuration

### GitHub Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Toolkit** | `github` | Toolkit under `alita_sdk/tools` |
| **Tool** | `get_commits` | Exact Python tool name |
| **Primary Input(s)** | `{{SHA}}, {{PATH}}, {{SINCE}}, {{UNTIL}}, {{AUTHOR}}, {{MAX_COUNT}}` | Optional filters |
| **Expected Result** | `{{EXPECTED_COMMIT_LIST}}` | List of dicts with `sha`, `author`, `date`, `message`, `url`, size ≤ `max_count` |

## Config

path: .alita\tool_configs\git-config.json
generateTestData: false

## Pre-requisites

- Repo has commit history

## Test Steps & Expectations

### Step 1: Execute the Tool

Run `get_commits` with `max_count=5`, `sha=main`

**Expectation:** returns list of up to 5 commits.

### Step 2: Verify Core Output Contract

Each commit dict includes keys: `sha`, `author`, `date`, `message`, `url`.