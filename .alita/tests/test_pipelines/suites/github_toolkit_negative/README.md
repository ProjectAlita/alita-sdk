# GitHub Toolkit Negative Tests

Tests for error handling, edge cases, and graceful failure scenarios in the GitHub toolkit.

## Purpose

Verify that the GitHub toolkit returns **actionable error messages** that allow LLM agents to:
1. Understand what went wrong
2. Know how to recover or retry
3. Not receive raw Python tracebacks

## Test Categories

| Category | Pipeline | Tests | What's Tested |
|----------|----------|-------|---------------|
| **All** | `pipeline.yaml` | 20 | All negative tests |
| **Not Found (404)** | `pipeline_not_found.yaml` | 6 | Non-existent resources |
| **Validation** | `pipeline_validation.yaml` | 10 | Invalid inputs (including update_file) |
| **Conflicts** | `pipeline_conflicts.yaml` | 4 | Duplicate/conflict errors |

## Running Tests

```bash
# Run ALL negative tests
alita agent execute-test-cases --suite github_toolkit_negative

# Run only 404/Not Found tests
alita agent execute-test-cases --suite github_toolkit_negative_not_found

# Run only validation tests
alita agent execute-test-cases --suite github_toolkit_negative_validation

# Run only conflict tests
alita agent execute-test-cases --suite github_toolkit_negative_conflicts
```

## Test Structure

```
github_toolkit_negative/
├── pipeline.yaml                 # Main suite (runs all)
├── pipeline_not_found.yaml       # 404 errors only
├── pipeline_validation.yaml      # Validation errors only
├── pipeline_conflicts.yaml       # Conflict errors only
├── README.md                     # This file
└── tests/
    ├── not_found/               # 404 error tests
    │   ├── test_neg_05_nonexistent_issue.yaml
    │   ├── test_neg_06_nonexistent_repo.yaml
    │   ├── test_neg_07_nonexistent_file.yaml
    │   ├── test_neg_08_nonexistent_branch.yaml
    │   ├── test_neg_09_nonexistent_pr.yaml
    │   └── test_neg_10_nonexistent_commit.yaml
    ├── validation/              # Input validation tests
    │   ├── test_neg_14_invalid_repo_format.yaml
    │   ├── test_neg_15_invalid_issue_number.yaml
    │   ├── test_neg_16_empty_file_path.yaml
    │   ├── test_neg_17_invalid_branch_name.yaml
    │   ├── test_neg_18_create_branch_from_nonexistent.yaml
    │   ├── test_neg_30_update_file_missing_old_marker.yaml
    │   ├── test_neg_31_update_file_missing_new_marker.yaml
    │   ├── test_neg_32_update_file_old_not_found.yaml
    │   ├── test_neg_33_update_file_empty_query.yaml
    │   └── test_neg_34_update_file_no_newline.yaml
    └── conflicts/               # Conflict/duplicate tests
        ├── test_neg_21_branch_already_exists.yaml
        ├── test_neg_22_file_already_exists.yaml
        ├── test_neg_24_merge_with_conflicts.yaml
        └── test_neg_25_pr_same_head_base.yaml
```

## What Each Test Validates

Every test checks that the error response:

1. **Indicates failure** - Contains "not found", "error", "failed", etc.
2. **References the resource** - Mentions what type of resource failed
3. **No raw tracebacks** - Clean message, not Python stack traces
4. **Not a success response** - Doesn't return data as if operation succeeded
5. **Is concise** - Under 1000 chars, not a data dump

## Test Output Format

Each test produces a result like:

```json
{
  "test_passed": true,
  "error_quality": {
    "indicates_not_found": true,
    "references_resource_type": true,
    "no_raw_traceback": true,
    "not_success_response": true,
    "is_concise": true
  },
  "actual_response": "Failed to get issue: Issue #999999999 not found",
  "improvement_needed": []
}
```

## Adding New Tests

1. Choose the appropriate category folder
2. Create a YAML file following the naming pattern: `test_neg_XX_description.yaml`
3. Use the validation code pattern from existing tests
4. Add the test to the appropriate `pipeline_*.yaml` order list
