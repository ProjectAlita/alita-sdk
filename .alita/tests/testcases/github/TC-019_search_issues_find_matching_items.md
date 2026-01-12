# search_issues: Find matching issues and pull requests

## Priority

Critical

## Objective

Verify that `search_issues` returns issues/PRs matching a repository-scoped query and respects `max_count`.

## Test Data Configuration

### GitHub Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Toolkit** | `github` | Toolkit under `alita_sdk/tools` |
| **Tool** | `search_issues` | Exact Python tool name |
| **Primary Input(s)** | `is:issue state:open`, `ProjectAlita/elitea-testing`, `1` | Query string, repo scope, and max result count |
| **Expected Result** | `AI issue for comments` | At least one returned item title contains this value |

## Config

path: .alita\tool_configs\git-config.json
generateTestData: false

## Pre-requisites

- Valid configuration for toolkit `github`
- Repository contains at least one issue or PR matching `is:issue state:open` with title including `AI issue for comments`

## Test Steps & Expectations

### Step 1: Execute the Tool

Execute the github toolkit tool `search_issues` tool with:
```
{
  "search_query": "state:open",
  "repo_name": "ProjectAlita/elitea-testing",
  "max_count": 1
}
```

**Expectation:** The tool runs without errors and returns a list of items.

### Step 2: Verify Core Output Contract

Inspect the output list.

**Expectation:** At least one item includes title containing `AI issue for comments`; total results do not exceed `1`.