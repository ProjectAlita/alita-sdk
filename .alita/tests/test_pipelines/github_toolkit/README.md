# GitHub Toolkit Test Suite

This directory contains a complete test suite for validating GitHub toolkit functionality through the Alita SDK.

## Directory Structure

```
github_toolkit/
├── pipeline.yaml          # Main suite configuration
├── tests/                 # Test case files
│   ├── test_case_1_list_branches.yaml
│   ├── test_case_2_set_active_branch.yaml
│   └── ...
├── configs/               # Suite-specific configurations
│   └── git-config.json   # GitHub toolkit base configuration
├── composables/           # Reusable composable pipelines
│   └── rca_on_failure.yaml  # Root cause analysis pipeline
└── README.md
```

## Overview

These tests validate GitHub toolkit operations by declaring toolkits as pipeline participants and invoking tools via toolkit nodes or code nodes. Tests are organized from read-only operations to write operations.

## Pipeline Structure

Each pipeline uses the new toolkit participant structure:

```yaml
name: "GH1 - List Branches"
description: "Description..."

toolkits:
  - id: ${GITHUB_TOOLKIT_ID}  # Substituted during seeding
    name: github              # Reference name for code nodes

state:
  ...

nodes:
  - id: my_node
    type: code
    code:
      type: fixed
      value: |
        # Access toolkit via toolkits dict
        github_toolkit = toolkits.get('github')
        tools = github_toolkit.get_tools()
        ...
```

## Prerequisites

1. **GitHub Toolkit configured** - A GitHub toolkit must be created in the project with:
   - Valid GitHub access token
   - Repository configured (e.g., `ProjectAlita/elitea-testing`)
   - Appropriate permissions for read/write operations

2. **Environment Variable** - Set `GITHUB_TOOLKIT_ID` in environment or `.env` file:
   ```bash
   export GITHUB_TOOLKIT_ID=1
   ```

3. **Test Repository** - Tests expect a repository with:
   - `main` branch
   - At least one issue
   - `.gitignore` file
   - Branch `tc-file-ops-2025-12-08` for write operations

## Suite Configuration (pipeline.yaml)

The `pipeline.yaml` file defines:

- **Setup Steps**: Automated toolkit creation, branch creation, test data setup
- **Composable Pipelines**: RCA (Root Cause Analysis) pipeline for test failures
- **Test Execution**: Test directory (`tests/`), execution order, variable substitutions
- **Cleanup Steps**: Automated teardown of test artifacts
- **Hooks**: Post-test hooks like RCA on failure

This configuration makes the suite self-contained and portable - just provide credentials and run!

## Running the Suite

The suite provides three main scripts that work together:

### 1. Setup - Prepare Environment

```bash
cd /path/to/alita-sdk/.alita/tests/test_pipelines
python setup.py github_toolkit
```

This reads `pipeline.yaml` and executes setup steps:
- Creates/verifies GitHub toolkit configuration
- Creates test branch
- Creates test issue
- Sets up SDK analysis toolkit for RCA

Environment variables are saved for the next steps.

### 2. Seed - Create Test Pipelines

```bash
export GITHUB_TOOLKIT_ID=80 SDK_TOOLKIT_ID=81  # From setup output
python seed_pipelines.py github_toolkit
```

This creates:
- Composable pipelines (RCA) - seeded first
- Test pipelines (GH1-GH10) - linked to GitHub toolkit
- Variable substitution from environment

### 3. Run - Execute Tests

```bash
export RCA_PIPELINE_ID=575  # From seed output
python run_suite.py github_toolkit
```

This executes tests and triggers hooks (RCA on failures).

### 4. Cleanup - Remove Artifacts

```bash
python cleanup.py github_toolkit --yes
```

This removes all created pipelines, branches, and test data.

## Test Cases

| Test | Name | Description | Type |
|------|------|-------------|------|
| GH1 | List Branches | Verify `list_branches_in_repo` returns branch list | Read |
| GH2 | Set Active Branch | Verify `set_active_branch` switches working branch | Read |
| GH3 | Read File | Verify `read_file` retrieves file content | Read |
| GH4 | Get Issues | Verify `get_issues` returns issue list | Read |
| GH5 | Get Issue | Verify `get_issue` returns specific issue details | Read |
| GH6 | Get Commits | Verify `get_commits` returns commit history | Read |
| GH7 | List Pull Requests | Verify `list_pull_requests` returns PR list | Read |
| GH8 | Create Branch | Verify `create_branch` creates new feature branch | Write |
| GH9 | Create File | Verify `create_file` creates file in branch | Write |
| GH10 | Create PR | Verify `create_pull_request` creates pull request | Write |

## Test Organization

### Read Operations (GH1-GH7)
These tests are safe to run repeatedly without side effects:
- List branches, issues, commits, PRs
- Read files from repository
- Switch active branch

### Write Operations (GH8-GH10)
These tests modify the repository:
- **GH8**: Creates a new branch with timestamp suffix
- **GH9**: Creates a file in the `tc-file-ops-2025-12-08` branch
- **GH10**: Creates a PR from feature branch to main

## Dependent Test Flow

For integrated testing, run tests in sequence:
```
GH1 → GH2 → GH3 → GH4 → GH5 → GH6 → GH7 → GH8 → GH9 → GH10
```

Or for a complete write workflow:
```
GH8 (create branch) → GH2 (set branch) → GH9 (create file) → GH10 (create PR)
```

## Code Node Pattern

All tests use this pattern to access toolkit tools:

```python
# Get toolkit from pipeline participants
github_toolkit = toolkits.get('github')
if github_toolkit:
    tools = github_toolkit.get_tools()

    # Find specific tool
    for tool in tools:
        if tool.name == 'list_branches_in_repo':
            result = tool.invoke({})
            break
```

## Configuration

State variables can be customized per test:

| Variable | Default | Description |
|----------|---------|-------------|
| `target_branch` | `main` or `tc-file-ops-2025-12-08` | Branch for operations |
| `issue_number` | 1 | Issue number for GH5 |
| `max_count` | 5 | Commit limit for GH6 |
| `file_path` | `.gitignore` | File to read in GH3 |

## Expected Results

Each test outputs a `test_results` dict with:
- `test_passed`: Boolean indicating overall success
- `tool_executed`: Whether the tool was invoked successfully
- Operation-specific results and validation checks
- `error`: Error message if any failure occurred

## Troubleshooting

### Common Issues

1. **"GitHub toolkit not found in pipeline participants"**
   - Verify `GITHUB_TOOLKIT_ID` is set correctly
   - Re-seed pipelines with correct toolkit ID
   - Check toolkit exists in the project

2. **"tool not found in toolkit"**
   - Verify toolkit has the required tools enabled
   - Check tool name matches exactly

3. **Authentication errors**
   - Verify GitHub access token is valid in toolkit config
   - Check token has required permissions (repo scope)

4. **"Branch not found"**
   - Create the test branch `tc-file-ops-2025-12-08` in the repository
   - Or update `target_branch` in state

5. **"PR already exists"**
   - This is expected if running GH10 multiple times
   - Test handles this as a passing condition
