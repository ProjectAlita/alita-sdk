# get_commits_diff: compare two commits

## Priority

Critical

## Objective

Compare two commit SHAs and validate diff summary and files.

## Test Data Configuration

### GitHub Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Toolkit** | `github` | Toolkit under `alita_sdk/tools` |
| **Tool** | `get_commits_diff` | Exact Python tool name |
| **Primary Input(s)** | `{{BASE_SHA}}, {{HEAD_SHA}}` | Base and head commit SHAs |
| **Expected Result** | `{{EXPECTED_DIFF_SUMMARY}}` | Dict includes `base_commit`, `head_commit`, `status`, `ahead_by`, `behind_by`, `total_commits`, `files`, `summary` |

## Config

path: .alita\tool_configs\git-config.json
generateTestData: true

## Pre-requisites

- Commits exist and are comparable

## Test Steps & Expectations

### Step 1: Execute the Tool

Run `get_commits_diff` with supplied SHAs.

**Expectation:** returns diff dict.

### Step 2: Verify Core Output Contract

Confirm summary stats and file entries structure.