# apply_git_patch: apply unified diff

## Priority

Critical

## Objective

Apply a valid unified diff patch and verify applied changes summary.

## Test Data Configuration

### GitHub Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Toolkit** | `github` | Toolkit under `alita_sdk/tools` |
| **Tool** | `apply_git_patch` | Exact Python tool name |
| **Primary Input(s)** | `{{PATCH_CONTENT}}, {{COMMIT_MESSAGE}}` | Patch text and commit message |
| **Expected Result** | `{{EXPECTED_PATCH_RESULT}}` | Dict includes `success`, `applied_changes`, `failed_changes`, `total_changes`, `message` |

## Config

path: .alita\tool_configs\git-config.json
generateTestData: true

## Pre-requisites

- Active branch is not base

## Test Steps & Expectations

### Step 1: Execute the Tool

Run `apply_git_patch` using a small create/modify patch.

**Expectation:** returns result dict.

### Step 2: Verify Core Output Contract

Check counts and that `message` summarises success/partial.