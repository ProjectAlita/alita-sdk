# create_pull_request: open PR creation

## Priority

Critical

## Objective

Create a pull request from active branch to base and verify success message.

## Test Data Configuration

### GitHub Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Toolkit** | `github` | Toolkit under `alita_sdk/tools` |
| **Tool** | `create_pull_request` | Exact Python tool name |
| **Primary Input(s)** | `{{HEAD}}` | PR title, body, head branch, base branch (use `main` for `{{BASE}}`) |
| **Expected Result** | `{{EXPECTED_PR_CREATE_MESSAGE}}` | Message contains `Pull request created successfully! PR #` and `URL:` |

## Config

path: .alita\tool_configs\git-config.json
generateTestData: true

## Pre-requisites

- Valid config and credentials
- Head branch exists and differs from base

## Test Steps & Expectations

### Step 1: List existing PRs and remember count

- Run the `list_pull_requests` (or equivalent) tool for the repository with `base` set to `main`.
- Record the number of open PRs returned (store as `INITIAL_PR_COUNT`).

**Expectation:** tool returns a list; `INITIAL_PR_COUNT` is recorded.

### Step 2: Create pull request using `main` as base

- Run `create_pull_request` with the following inputs:

	- `title`: `AI created PR {{RANDOM_STRING}}`
	- `body`: `PR created by AI for testing purposes.`
	- `head`: `{{HEAD}}`
	- `base`: `main`

**Expectation:** `create_pull_request` returns a success message indicating the PR was created.

### Step 3: Verify PR count increased

- Run `list_pull_requests` again for the repository with `base` = `main` and record the count as `NEW_PR_COUNT`.
- Assert `NEW_PR_COUNT` == `INITIAL_PR_COUNT + 1` (or increased by the number of PRs created in this test).

**Expectation:** the number of open PRs targeting `main` has increased.

### Step 4: Check create PR tool output

- Inspect the output of the `create_pull_request` tool used in Step 2.
- Assert the output string includes `Pull request created successfully! PR #` and `URL:` and that the returned URL points to a PR whose base is `main`.

**Expectation:** tool output contains the expected success message and URL; the created PR targets `main`.