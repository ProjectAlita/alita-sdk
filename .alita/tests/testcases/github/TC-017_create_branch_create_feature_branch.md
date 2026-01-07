# create_branch: Create a feature branch for work

## Priority

Critical

## Objective

Verify that `create_branch` creates a new branch starting from the base branch and sets it active for default repo.

## Test Data Configuration

### GitHub Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Toolkit** | `github` | Toolkit under `alita_sdk/tools` |
| **Tool** | `create_branch` | Exact Python tool name |
| **Primary Input(s)** | `{{PROPOSED_BRANCH_NAME}}` | Desired branch name to create |

## Config

path: .alita\tool_configs\git-config.json
generateTestData: true

## Pre-requisites

- Valid configuration for toolkit `github`
- Environment provides `GITHUB_REPOSITORY`, `GITHUB_ACCESS_TOKEN`, `GITHUB_BASE_BRANCH`
- Proposed branch name does not already exist; otherwise tool will prefix `ALITA-` and create a unique branch

## Test Steps & Expectations

### Step 1: Execute the Tool

Execute the `create_branch` tool with:
- `proposed_branch_name`: `{{PROPOSED_BRANCH_NAME}}`

**Expectation:** The tool runs without errors and returns a success message.

### Step 2: Verify Core Output Contract

Inspect the output.

**Expectation:** The message contains `Branch '{{PROPOSED_BRANCH_NAME}}' created successfully` and, for default repo, mentions set as active branch.

### Step 3: Switch to the New Branch

Execute the `set_active_branch` tool with:
- `branch_name`: `{{PROPOSED_BRANCH_NAME}}`

**Expectation:** The tool runs without errors and returns a success message.