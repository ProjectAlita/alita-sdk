# GitHub Toolkit Test Suite

Comprehensive test coverage for GitHub toolkit operations with atomic, independent tests.

## Directory Structure

```
github_toolkit/
├── pipeline.yaml          # Main suite configuration
├── tests/                 # Test case files (25 atomic tests)
│   ├── test_case_01_list_branches.yaml
│   ├── test_case_02_commits_workflow.yaml
│   ├── test_case_03_list_pull_requests.yaml
│   ├── test_case_04_search_issues.yaml
│   ├── test_case_05_generic_api_call.yaml
│   ├── test_case_06_project_issue_workflow.yaml
│   ├── test_case_07_update_file_single_line.yaml
│   ├── ... (18 more sequential tests)
│   └── test_case_25_get_files_from_dir.yaml
├── configs/               # Suite-specific configurations
│   └── github-config.json # GitHub toolkit base configuration
├── composables/           # Reusable composable pipelines
│   └── rca_on_failure.yaml  # Root cause analysis pipeline
└── README.md
```

## Overview

This suite validates GitHub toolkit operations through **25 atomic, independent tests**. After restructuring, all tests are self-contained, focusing on single operations with clear objectives and proper cleanup.

## Pipeline Structure

Each pipeline uses the new toolkit participant structure:

```yaml
name: "GH07 - Update File Single Line"
description: "Test update_file with single line replacement"

toolkits:
  - id: ${GITHUB_TOOLKIT_ID}  # Substituted during execution
    name: ${GITHUB_TOOLKIT_NAME}  # Reference name

state:
  ...

nodes:
  - id: my_node
    type: toolkit
    tool: update_file
    toolkit_name: ${GITHUB_TOOLKIT_NAME}
    ...
```
## Prerequisites

1. **GitHub Toolkit configured** - A GitHub toolkit must be created in the project with:
   - Valid GitHub access token
   - Repository configured (e.g., `ProjectAlita/elitea-testing`)
   - Appropriate permissions for read/write operations

2. **Environment Variables** - Set in `.env` file:
   ```bash
   GITHUB_TOOLKIT_ID=your_toolkit_id
   GITHUB_TOOLKIT_NAME=github
   GITHUB_TOKEN=ghp_your_token_here
   GITHUB_REPOSITORY=owner/repo
   ```

3. **Test Repository** - Tests expect a repository with:
   - `main` branch
   - At least one issue
   - Standard files (`.gitignore`, `README.md`, etc.)

## Suite Configuration (pipeline.yaml)

The `pipeline.yaml` file defines:

- **Setup Steps**: Automated toolkit creation, test data setup
- **Composable Pipelines**: RCA (Root Cause Analysis) pipeline for test failures
- **Test Execution**: Test directory (`tests/`), test pattern, variable substitutions
- **Cleanup Steps**: Automated teardown of test artifacts
- **Hooks**: Post-test hooks like RCA on failure

This configuration makes the suite self-contained and portable - just provide credentials and run!
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

## Test Inventory

### Core Tests (Original - Kept)

| Test ID | File | Description | Size | Status |
|---------|------|-------------|------|--------|
| **GH01** | test_case_01_list_branches.yaml | List repository branches | 1.9K | ✅ Atomic |
| **GH02** | test_case_02_commits_workflow.yaml | Get commits and diffs | 6.2K | ✅ Atomic |
| **GH03** | test_case_03_list_pull_requests.yaml | List open pull requests | 2.3K | ✅ Atomic |
| **GH04** | test_case_04_search_issues.yaml | Search issues by query | 2.7K | ✅ Atomic |
| **GH05** | test_case_05_generic_api_call.yaml | Generic GitHub API calls | 3.0K | ✅ Atomic |
| **GH06** | test_case_06_project_issue_workflow.yaml | Project board operations | 12K | ✅ Functional |

### Update File Operations (New Atomic Tests)

| Test ID | File | Description | Size |
|---------|------|-------------|------|
| **GH07** | test_case_07_update_file_single_line.yaml | Single line replacement | 5.6K |
| **GH08** | test_case_08_update_file_multiline.yaml | Multiline code block updates | 7.0K |
| **GH09** | test_case_09_update_file_json.yaml | JSON/structured content updates | 6.0K |
| **GH10** | test_case_10_update_file_special_chars.yaml | Special character handling | 5.9K |
| **GH11** | test_case_11_update_file_error_handling.yaml | Error handling (OLD not found) | 5.7K |
| **GH12** | test_case_12_update_file_whitespace.yaml | Whitespace tolerance matching | 5.7K |
| **GH13** | test_case_13_update_file_empty_replace.yaml | Empty replacement (deletion) | 5.7K |

### File Operations (New Atomic Tests)

| Test ID | File | Description | Size |
|---------|------|-------------|------|
| **GH14** | test_case_14_create_file.yaml | Create file with content | 4.6K |
| **GH15** | test_case_15_apply_git_patch.yaml | Apply git patch to modify file | 6.4K |

### Issue Operations (New Atomic Tests)

| Test ID | File | Description | Size |
|---------|------|-------------|------|
| **GH16** | test_case_16_create_issue.yaml | Create new issue | 3.8K |
| **GH17** | test_case_17_comment_on_issue.yaml | Add comment to issue | 2.3K |
| **GH18** | test_case_18_list_issues.yaml | List open issues | 1.8K |
| **GH19** | test_case_19_get_issue.yaml | Get issue details | 1.9K |

### Pull Request Operations (New Atomic Tests)

| Test ID | File | Description | Size |
|---------|------|-------------|------|
| **GH20** | test_case_20_create_pull_request.yaml | Create new pull request | 5.7K |
| **GH21** | test_case_21_get_pull_request.yaml | Get PR details | 1.9K |
| **GH22** | test_case_22_list_pr_diffs.yaml | List PR file diffs | 1.8K |

### File Reading Operations (New Atomic Tests)

| Test ID | File | Description | Size |
|---------|------|-------------|------|
| **GH23** | test_case_23_read_file.yaml | Read file content | 1.9K |
| **GH24** | test_case_24_list_files_branch.yaml | List files in branch | 1.8K |
| **GH25** | test_case_25_get_files_from_dir.yaml | Get files from directory | 1.8K |

## Test Statistics

- **Total Tests:** 25
- **Atomic Tests:** 25 (100%)
- **Average Size:** ~4.2K
- **Largest Test:** 12K (GH06 - project operations)
- **Smallest Test:** 1.8K (GH18, GH22, GH24, GH25)

## Deprecated Tests (Removed)

The following tests were split into atomic tests and removed:

| Original Test | Size | Replaced By | Reason |
|--------------|------|-------------|---------|
| test_case_02_file_reading.yaml | 300 lines | GH23-GH25 | Combined list+get+read |
| test_case_03_issue_workflow.yaml | 448 lines | GH16-GH19 | Combined create+list+get+comment |
| test_case_06_file_operations.yaml | 375 lines | GH14-GH15 | Combined create+patch |
| test_case_07_pull_request_workflow.yaml | 320 lines | GH20-GH22 | Combined create+get+diffs |
| test_case_08_update_file.yaml | 1488 lines | GH07-GH13 | Combined 7 update scenarios |

## Running Tests

### Run Individual Test
```bash
cd .alita/tests/test_pipelines
./run_test.sh --local suites/github GH07
```

### Run Test Category
```bash
# All update_file tests
./run_test.sh --local suites/github GH07,GH08,GH09,GH10,GH11,GH12,GH13

# All issue tests
./run_test.sh --local suites/github GH16,GH17,GH18,GH19

# All PR tests
./run_test.sh --local suites/github GH20,GH21,GH22

# All file reading tests
./run_test.sh --local suites/github GH23,GH24,GH25
```

### Run All Tests
```bash
./run_test.sh --local suites/github
```

## Test Design Principles

Each atomic test follows this pattern:

1. **Setup** - Generate unique test data (timestamps, random IDs)
2. **Prerequisites** - Create required resources (branches, files)
3. **Execute** - Run the tool being tested
4. **Validate** - LLM-based result verification
5. **Cleanup** - Delete created resources (with `continue_on_error: true`)

**Key Features:**
- ✅ One test = one tool operation
- ✅ Self-contained (creates own test data)
- ✅ Independent (no test dependencies)
- ✅ Parallel execution ready
- ✅ Proper cleanup with error handling
- ✅ Clear pass/fail validation

## Coverage by Tool

| Tool | Tests | Coverage |
|------|-------|----------|
| update_file | GH07-GH13 | 7 scenarios ✅ |
| create_file | GH14 | ✅ |
| apply_git_patch | GH15 | ✅ |
| create_issue | GH16 | ✅ |
| comment_on_issue | GH17 | ✅ |
| get_issues | GH18 | ✅ |
| get_issue | GH19 | ✅ |
| create_pull_request | GH20 | ✅ |
| get_pull_request | GH21 | ✅ |
| list_pull_request_diffs | GH22 | ✅ |
| read_file | GH23 | ✅ |
| list_files_in_main_branch | GH24 | ✅ |
| get_files_from_directory | GH25 | ✅ |
| list_branches_in_repo | GH01 | ✅ |
| get_commits | GH02 | ✅ |
| get_commits_diff | GH02 | ✅ |
| list_open_pull_requests | GH03 | ✅ |
| search_issues | GH04 | ✅ |
| generic_github_api_call | GH05 | ✅ |
| *_project_* tools | GH06 | ✅ |

**Total Coverage:** 20+ tools with 25 independent tests

---
