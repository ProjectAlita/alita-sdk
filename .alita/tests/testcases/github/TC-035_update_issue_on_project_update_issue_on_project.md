# update_issue_on_project: update issue on project

## Priority

Critical

## Objective

Update title/body and fields on an existing project issue.

## Test Data Configuration

### GitHub Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Toolkit** | `github` | Toolkit under `alita_sdk/tools` |
| **Tool** | `update_issue_on_project` | Exact Python tool name |
| **Primary Input(s)** | `{{BOARD_REPO}}=AI_testing_board, {{ISSUE_NUMBER}}=20, {{PROJECT_TITLE}}=AI_testing_board, {{TITLE}}=AI title {{RANDOM_STRING}}, {{BODY}}=dummy comment {{RANDOM_STRING}}.` | Inputs per args_schema |

## Config

path: .alita\tool_configs\git-config.json
generateTestData: false

## Pre-requisites

- Issue exists in project

## Test Steps & Expectations

### Step 1: Execute the Tool

Run `update_issue_on_project` with the following arguments 
 - Board Repo ProjectAlita/elitea-testing
 - Issue Number 20
 - Project Title AI_testing_board
 - New Title AI title {{RANDOM_STRING}}
 - Body dummy comment {{RANDOM_STRING}}.

**Expectation:** returns message string.

### Step 2: Verify Core Output Contract

Validate message starts with `The issue with number` and optional fields summary.