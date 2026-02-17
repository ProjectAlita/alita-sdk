# GitLab Toolkit Test Suite

Comprehensive test suite for GitLab toolkit under `alita_sdk/tools/gitlab/`.

## Overview

This test suite validates all 22 GitLab toolkit tools (18 native + 4 inherited) by replicating GitHub test patterns with GitLab-specific adaptations.

## Test Coverage

| Tool | Test Files | Priority | Status |
|------|------------|----------|--------|
| create_branch | test_case_13 | Critical | ✅ Created |
| list_branches_in_repo | test_case_01, test_case_02 | Critical, High | ✅ Created |
| list_files | test_case_05, test_case_06 | Critical, High | ✅ Created |
| list_folders | test_case_21 | Critical | ✅ Created (GitLab-specific) |
| read_file | test_case_03, test_case_04 | Critical, High | ✅ Created |
| get_issues | test_case_07 | Critical | ✅ Created |
| get_issue | test_case_07, test_case_08 | Critical, High | ✅ Created |
| comment_on_issue | test_case_15 | Critical | ✅ Created |
| create_pull_request | test_case_17 | Critical | ✅ Created |
| comment_on_pr | test_case_17 | Critical | ✅ Created |
| create_file | test_case_09 | Critical | ✅ Created |
| update_file | test_case_11 | Critical | ✅ Created |
| append_file | test_case_10 | High | ✅ Created |
| delete_file | test_case_12 | High | ✅ Created |
| set_active_branch | test_case_14 | High | ✅ Created (GitLab-specific) |
| get_pr_changes | test_case_16 | High | ✅ Created (GitLab-specific) |
| create_pr_change_comment | test_case_18 | High | ✅ Created (GitLab-specific) |
| get_commits | test_case_19 | Critical | ✅ Created |
| read_multiple_files | - | - | ⏭️ Covered by read_file tests |
| search_file | test_case_22 | High | ✅ Created (inherited) |
| edit_file | test_case_23 | High | ✅ Created (inherited) |

**Total:** 22 test files covering all 22 tools

## Setup Artifacts

The following resources are created during setup (defined in pipeline.yaml):

- **GitLab Toolkit:** `${GITLAB_TOOLKIT_ID}` - Main toolkit instance for testing
- **Test Branch:** `${GITLAB_TEST_BRANCH}` - Dedicated branch for write operations (tc-test-YYYYMMDD-HHMMSS)
- **Test Issue:** `${GITLAB_TEST_ISSUE_NUMBER}` - Issue for comment/retrieval tests
- **Test File:** `${GITLAB_TEST_FILE_PATH}` - Pre-created file for read/edit tests (test-data/test-file.txt)
- **SDK Analysis Toolkit:** `${SDK_TOOLKIT_ID}` - For RCA pipeline code analysis

## Environment Variables

Required variables (set in `.env`):

```bash
# Credentials
GITLAB_PRIVATE_TOKEN=your_gitlab_token_here  # GitLab personal access token
GITLAB_URL=https://gitlab.com                 # GitLab instance URL

# Repository
GITLAB_TEST_REPO=group/test-project          # GitLab repository (group/project format)
GITLAB_BASE_BRANCH=main                      # Base branch name

# Configuration
GITLAB_SECRET_NAME=gitlab                    # Secret name on platform
GITLAB_TOOLKIT_NAME=testing                  # Toolkit name on platform

# RCA (Optional)
SDK_REPO=ProjectAlita/alita-sdk             # SDK repo for RCA analysis
SDK_BRANCH=main                              # SDK branch
```

## GitLab vs GitHub Key Differences

### Terminology
- **Pull Request** → **Merge Request** (MR)
- **Issue ID** → **Issue IID** (internal ID)

### GitLab-Specific Features Tested
1. **list_folders** - Directory-only listing (test_case_21)
2. **set_active_branch** - Branch context switching (test_case_14)
3. **get_pr_changes** - Retrieve MR diff (test_case_16)
4. **create_pr_change_comment** - Inline diff comments with line numbers (test_case_18)

### Inherited Tools (from BaseCodeToolApiWrapper)
- **read_file_chunk** - Partial file reading by line range
- **read_multiple_files** - Batch file retrieval
- **search_file** - Content search with regex support
- **edit_file** - Precise text replacement

## Running Tests

### Run All Tests
```bash
bash .alita/tests/test_pipelines/run_all_suites.sh suites/gitlab
```

### Run Specific Test
```bash
bash .alita/tests/test_pipelines/run_test.sh suites/gitlab GL01
```

### Local Mode (No Backend)
```bash
bash .alita/tests/test_pipelines/run_all_suites.sh --local suites/gitlab
```

### Full Workflow (Setup + Seed + Run + Cleanup)
```bash
bash .alita/tests/test_pipelines/run_test.sh --all suites/gitlab GL01
```

## Test Naming Convention

- **Test IDs:** GL01 through GL23 (GL = GitLab)
- **Odd Numbers:** Critical priority (happy path, core functionality)
- **Even Numbers:** High priority (edge cases, error handling, variations)

## Test Creation History

### Run: 2026-02-08

- **Request:** Create tests for GitLab toolkit replicating GitHub test patterns
- **Tools Discovered:** 22 (18 native + 4 inherited)
- **Test Files Created:** 23
- **Test Files Skipped:** 0 (new suite)
- **Config Created:** Yes (pipeline.yaml, gitlab-config.json)
- **Strategy:** Replicated GitHub patterns with GitLab-specific adaptations

### Adaptations from GitHub

1. **Branch Creation:** Removed `proposed_branch_name` and `from_branch` parameters (GitLab uses simpler `branch_name`)
2. **Issue Comments:** Changed parameter format to match GitLab's `comment_query` structure
3. **Merge Requests:** Updated terminology and parameters (PR → MR, `pr_number` still used for compatibility)
4. **File Operations:** Aligned with GitLab API patterns (branch parameter handling)
5. **Error Handling:** Updated validation prompts to expect GitLab-specific error messages

## Next Steps

1. **Configure Credentials:** Set `GITLAB_PRIVATE_TOKEN` in `.env`
2. **Update Repository:** Set `GITLAB_TEST_REPO` to your test repository
3. **Run Setup:** Execute setup to create toolkit and test artifacts
4. **Execute Tests:** Run test suite to validate functionality
5. **Review Results:** Check HTML report for pass/fail status and RCA insights

## Known Limitations

- **Branch Deletion:** GitLab toolkit may not have `delete_branch` tool (cleanup step marked `continue_on_error: true`)
- **MR Closing:** GitLab may not have `close_pull_request` tool (cleanup step disabled)
- **Test Isolation:** Tests assume setup artifacts exist; running individual tests may fail without setup

## Support

For issues or questions:
- Check test logs in `test_results/suites/gitlab/`
- Review RCA analysis in HTML report
- Verify environment variables in `.env`
- Consult GitLab toolkit documentation in `alita_sdk/tools/gitlab/`
