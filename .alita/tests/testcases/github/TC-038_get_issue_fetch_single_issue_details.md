# get_issue: fetch single issue details

## Priority

Critical

## Objective

Retrieve a specific issue by number and validate core fields.

## Test Data Configuration

### GitHub Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Toolkit** | `github` | Toolkit under `alita_sdk/tools` |
| **Tool** | `get_issue` | Exact Python tool name |
| **Primary Input(s)** | `{{ISSUE_NUMBER}}=21, {{REPO_NAME}}=ProjectAlita/elitea-testing` | Issue number and optional repo override |

## Config

path: .alita\tool_configs\git-config.json
generateTestData: true

## Pre-requisites

- Issue exists in repository

## Test Steps & Expectations

### Step 1: Execute the Tool

Run `get_issue` with `issue_number={{ISSUE_NUMBER}}`.

**Expectation:** returns dict without errors.

### Step 2: Verify Core Output Contract

Validate keys: `number`, `title`, `body`, `state`, `url`, `created_at`, `updated_at`, `labels`, `assignees`.
- `number`: matches `{{ISSUE_NUMBER}}`