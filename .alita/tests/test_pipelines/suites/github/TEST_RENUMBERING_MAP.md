# Test Renumbering Mapping

## Old Test Number → New Test Number

| Old # | New # | Test Name | Description |
|-------|-------|-----------|-------------|
| **01** | **01** | list_branches | List repository branches (unchanged) |
| **04** | **02** | commits_workflow | Get commits and diffs |
| **05** | **03** | list_pull_requests | List open pull requests |
| **09** | **04** | search_issues | Search issues by query |
| **10** | **05** | generic_api_call | Generic GitHub API calls |
| **11** | **06** | project_issue_workflow | Project board operations |
| **12** | **07** | update_file_single_line | Single line replacement |
| **13** | **08** | update_file_multiline | Multiline code block updates |
| **14** | **09** | update_file_json | JSON/structured content updates |
| **15** | **10** | update_file_special_chars | Special character handling |
| **16** | **11** | update_file_error_handling | Error handling (OLD not found) |
| **17** | **12** | update_file_whitespace | Whitespace tolerance matching |
| **18** | **13** | update_file_empty_replace | Empty replacement (deletion) |
| **19** | **14** | create_file | Create file with content |
| **20** | **15** | apply_git_patch | Apply git patch to modify file |
| **21** | **16** | create_issue | Create new issue |
| **22** | **17** | comment_on_issue | Add comment to issue |
| **23** | **18** | list_issues | List open issues |
| **24** | **19** | get_issue | Get issue details |
| **25** | **20** | create_pull_request | Create new pull request |
| **26** | **21** | get_pull_request | Get PR details |
| **27** | **22** | list_pr_diffs | List PR file diffs |
| **28** | **23** | read_file | Read file content |
| **29** | **24** | list_files_branch | List files in branch |
| **30** | **25** | get_files_from_dir | Get files from directory |

## Removed Tests (Not in New Numbering)

| Old # | Test Name | Status | Replaced By |
|-------|-----------|--------|-------------|
| **02** | file_reading | ❌ Removed | GH23-25 |
| **03** | issue_workflow | ❌ Removed | GH16-19 |
| **06** | file_operations | ❌ Removed | GH14-15 |
| **07** | pull_request_workflow | ❌ Removed | GH20-22 |
| **08** | update_file | ❌ Removed | GH07-13 |

## Summary

- **Total Tests:** 25 (sequential 01-25)
- **Unchanged:** 1 test (GH01)
- **Renumbered:** 24 tests
- **Removed:** 5 tests (split into atomic tests)

## Quick Reference for Test Execution

```bash
# Old way (gaps in numbering)
./run_test.sh --local suites/github GH12,GH13,GH14,GH15,GH16,GH17,GH18

# New way (sequential)
./run_test.sh --local suites/github GH07,GH08,GH09,GH10,GH11,GH12,GH13
```
