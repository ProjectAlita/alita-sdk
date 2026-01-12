# comment_on_issue: add comment to issue

## Priority

Critical

## Objective

Add a comment to an issue or PR and verify success message.

## Test Data Configuration

### GitHub Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Toolkit** | `github` | Toolkit under `alita_sdk/tools` |
| **Tool** | `comment_on_issue` | Exact Python tool name |
| **Primary Input(s)** | `{{ISSUE_NUMBER}}, {{COMMENT_TEXT}}, {{REPO_NAME}}=ProjectAlita/elitea-testing` | Target number, comment text, and repository name |

## Config

path: .alita\tool_configs\git-config.json
generateTestData: true

## Pre-requisites

- Comment permissions available

## Test Steps & Expectations

### Step 1: Execute the Tool

Run `comment_on_issue` with the following arguments 
 - Repo name ProjectAlita/elitea-testing
 - Issue Number {{ISSUE_NUMBER}}
 - Comment Text {{COMMENT_TEXT}}.

**Expectation:** returns success message.

### Step 2: Verify Core Output Contract

Ensure message contains `URL:`.