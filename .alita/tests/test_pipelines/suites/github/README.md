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

### Core Operations (GH1-GH10)

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
| GH8b | Delete Branch | Verify `delete_branch` removes branch with protections | Write |
| GH9 | Create File | Verify `create_file` creates file in branch | Write |
| GH10 | Create PR | Verify `create_pull_request` creates pull request | Write |

### Pull Request Operations (GH11-GH12)

| Test | Name | Description | Type |
|------|------|-------------|------|
| GH11 | Get Pull Request | Verify `get_pull_request` retrieves specific PR details | Read |
| GH12 | List PR Diffs | Verify `list_pull_request_diffs` retrieves file changes | Read |

### Issue Operations (GH13, GH18)

| Test | Name | Description | Type |
|------|------|-------------|------|
| GH13 | Comment on Issue | Verify `comment_on_issue` adds comment to issue | Write |
| GH18 | Search Issues | Verify `search_issues` finds matching issues/PRs | Read |

### File Operations (GH14-GH17)

| Test | Name | Description | Type |
|------|------|-------------|------|
| GH14 | Update File | Verify `update_file` modifies file using OLD/NEW format | Write |
| GH15 | Delete File | Verify `delete_file` removes file from branch | Write |
| GH16 | List Files Main Branch | Verify `list_files_in_main_branch` returns base branch files | Read |
| GH17 | Get Files from Directory | Verify `get_files_from_directory` lists directory contents | Read |

### Advanced Operations (GH19-GH21)

| Test | Name | Description | Type |
|------|------|-------------|------|
| GH19 | Get Commits Diff | Verify `get_commits_diff` compares two commits | Read |
| GH20 | Apply Git Patch | Verify `apply_git_patch` applies unified diff patch | Write |
| GH21 | Generic API Call | Verify `generic_github_api_call` calls supported methods | Read |

### Project Board Operations (GH22-GH25)

| Test | Name | Description | Type |
|------|------|-------------|------|
| GH22 | Create Issue on Project | Verify `create_issue_on_project` adds issue to board | Write |
| GH23 | List Project Issues | Verify `list_project_issues` retrieves board items | Read |
| GH24 | Update Issue on Project | Verify `update_issue_on_project` updates board item | Write |
| GH25 | Search Project Issues | Verify `search_project_issues` filters board items | Read |

## Test Organization

### Read Operations
These tests are safe to run repeatedly without side effects:
- **Core**: GH1 (branches), GH3 (file), GH4-GH5 (issues), GH6 (commits), GH7 (PRs)
- **PR Details**: GH11 (PR info), GH12 (PR diffs)
- **Files**: GH16 (main branch files), GH17 (directory files)
- **Search**: GH18 (search issues), GH19 (commits diff), GH21 (generic API)
- **Project**: GH23 (list items), GH25 (search items)

### Write Operations
These tests modify the repository:
- **GH2**: Sets active branch
- **GH8**: Creates a new branch with timestamp suffix
- **GH8b**: Deletes a branch (with protection for main/master/base branches)
- **GH9**: Creates a file in the `tc-file-ops-2025-12-08` branch
- **GH10**: Creates a PR from feature branch to main
- **GH13**: Comments on an issue
- **GH14**: Updates file content
- **GH15**: Deletes a file
- **GH20**: Applies a git patch
- **GH22**: Creates issue on project board
- **GH24**: Updates issue on project board

## Dependent Test Flow

For integrated testing, run tests in sequence:
```
GH1 → GH2 → GH3 → ... → GH25
```

Or for specific workflows:
```
# File operations workflow
GH8 (create branch) → GH2 (set branch) → GH9 (create file) → GH14 (update) → GH15 (delete) → GH8b (cleanup branch)

# PR workflow
GH8 (create branch) → GH9 (create file) → GH10 (create PR) → GH11 (get PR) → GH12 (diffs)

# Branch lifecycle workflow
GH8 (create branch) → GH2 (set branch) → ... operations ... → GH8b (delete branch)

# Project board workflow
GH22 (create item) → GH23 (list) → GH24 (update) → GH25 (search)
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
