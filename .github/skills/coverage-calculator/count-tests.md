# Count Test Cases

This procedure counts the number of test cases in a test suite by counting YAML files in the suite's test directory.

## Purpose

Determine how many test cases exist for a given toolkit to calculate test coverage metrics.

## Step-by-Step Procedure

### Step 1: Locate Test Suite Directory

Navigate to: `.alita/tests/test_pipelines/suites/{suite_name}/tests/`

**Examples**:
- GitHub tests: `.alita/tests/test_pipelines/suites/github_toolkit/tests/`
- JIRA tests: `.alita/tests/test_pipelines/suites/jira_toolkit/tests/`
- Postman tests: `.alita/tests/test_pipelines/suites/postman_toolkit/tests/`

**Suite Naming Convention**:
- Format: `{toolkit_name}_toolkit`
- Examples: `github_toolkit`, `confluence_toolkit`, `ado_toolkit`

### Step 2: List Test Files

List all files in the `tests/` subdirectory.

**Expected structure**:
```
suites/{suite_name}/
├── pipeline.yaml          # Suite configuration
├── README.md              # Suite documentation
└── tests/                 # Test cases directory
    ├── test_case_01_*.yaml
    ├── test_case_02_*.yaml
    └── ...
```

### Step 3: Filter Test Case Files

**Inclusion Criteria**:
- Filename matches pattern: `test_case_*.yaml`
- File extension is `.yaml` or `.yml`
- File is in the `tests/` subdirectory (not subdirectories)

**Exclusion Criteria**:
- Files not matching the `test_case_*` pattern
- Non-YAML files (`.md`, `.txt`, etc.)
- Files in subdirectories of `tests/`
- Hidden files (starting with `.`)
- Backup files (`.bak`, `~`, etc.)

**Examples**:
```
✅ test_case_01_get_issue.yaml          (INCLUDE)
✅ test_case_02_create_issue.yaml       (INCLUDE)
✅ test_case_10_list_repos.yaml         (INCLUDE)
❌ README.md                            (EXCLUDE - not YAML)
❌ config.yaml                          (EXCLUDE - wrong pattern)
❌ draft_test_case_99.yaml.bak          (EXCLUDE - backup file)
❌ tests/archived/test_case_old.yaml    (EXCLUDE - subdirectory)
```

### Step 4: Count Files

Count the total number of files that match the inclusion criteria.

**Counting Rules**:
- Each matching file counts as exactly 1 test case
- Do not count the same file multiple times
- Do not estimate based on numbering gaps
- Use actual file count (never assume)

**Example**:
```
test_case_01_get_issue.yaml
test_case_02_create_issue.yaml
test_case_05_update_issue.yaml    # Gap in numbering (03, 04 missing)
test_case_10_delete_issue.yaml
```
**Count**: 4 tests (not 10, despite numbering reaching 10)

### Step 5: Extract Test Metadata (Optional)

For detailed analysis, extract metadata from each test file:

- Test case number (from filename)
- Test name/description (from YAML `name` field)
- Tools being tested (from YAML content)
- Test status (from YAML or filename indicators)

## Expected Output

Provide results in this format:

```json
{
  "suite": "github_toolkit",
  "location": ".alita/tests/test_pipelines/suites/github_toolkit/tests/",
  "test_count": 12,
  "test_files": [
    "test_case_01_get_issue.yaml",
    "test_case_02_create_issue.yaml",
    "test_case_03_update_issue.yaml",
    "test_case_04_list_issues.yaml",
    "test_case_05_search_issues.yaml",
    "test_case_06_get_repo.yaml",
    "test_case_07_list_repos.yaml",
    "test_case_08_create_branch.yaml",
    "test_case_09_get_commit.yaml",
    "test_case_10_list_commits.yaml",
    "test_case_11_create_file.yaml",
    "test_case_12_update_file.yaml"
  ],
  "test_details": [
    {"file": "test_case_01_get_issue.yaml", "name": "Get Issue Details", "tools": ["get_issue"]},
    {"file": "test_case_02_create_issue.yaml", "name": "Create New Issue", "tools": ["create_issue"]}
  ]
}
```

## Common Patterns

### Pattern 1: Sequential Naming

```
test_case_01_*.yaml
test_case_02_*.yaml
test_case_03_*.yaml
```

**Count**: 3 tests

### Pattern 2: Numbering Gaps

```
test_case_01_*.yaml
test_case_02_*.yaml
test_case_05_*.yaml  # Gaps at 03, 04
test_case_10_*.yaml  # Gaps at 06-09
```

**Count**: 4 tests (count actual files, not max number)

### Pattern 3: Descriptive Suffixes

```
test_case_01_basic_functionality.yaml
test_case_02_error_handling.yaml
test_case_03_edge_cases.yaml
```

**Count**: 3 tests (suffix doesn't affect count)

### Pattern 4: Mixed Extensions

```
test_case_01_test.yaml   # ✅ Count
test_case_02_test.yml    # ✅ Count (both .yaml and .yml valid)
test_case_03_test.txt    # ❌ Don't count (not YAML)
```

**Count**: 2 tests

## Validation Checklist

- [ ] Confirmed suite directory exists
- [ ] Confirmed `tests/` subdirectory exists
- [ ] Listed all files in `tests/` directory
- [ ] Filtered to only `test_case_*.yaml` files
- [ ] Counted actual files (not estimated from numbering)
- [ ] Excluded non-YAML and non-matching files
- [ ] Excluded files in subdirectories

## Troubleshooting

**Problem**: Suite directory doesn't exist  
**Solution**: Toolkit may not have tests yet (report 0 tests)

**Problem**: `tests/` subdirectory is empty  
**Solution**: Suite exists but no tests created (report 0 tests)

**Problem**: Files don't match `test_case_*` pattern  
**Solution**: Check if suite uses different naming convention (document as exception)

**Problem**: Unsure if `.yml` files should be counted  
**Solution**: Yes, both `.yaml` and `.yml` are valid YAML extensions

**Problem**: Found `test_case_draft_*.yaml` files  
**Solution**: Still count them if they match `test_case_*.yaml` pattern

## Matching Tests to Tools

To understand **which tools** are tested:

1. Open each test case YAML file
2. Look for the `toolkit` and `tools` sections
3. Extract tool names being tested
4. Cross-reference with toolkit's available tools (see [count-tools.md](./count-tools.md))

**Example test case**:
```yaml
name: Get Issue Details
toolkit: github
tools:
  - get_issue
test:
  - action: get_issue
    params:
      repo: test/repo
      issue_number: 1
```

This test covers the `get_issue` tool.

## Coverage Calculation

With test and tool counts:

```
Tools Tested = (Unique tools across all test cases)
Total Tools = (From get_available_tools())
Coverage % = (Tools Tested / Total Tools) × 100
```

See [skill.md](./skill.md) for complete calculation formulas.

## Related Procedures

- [count-tools.md](./count-tools.md) - Count tools in toolkit
- [categorize-toolkit.md](./categorize-toolkit.md) - Determine toolkit category
- [skill.md](./skill.md) - Main coverage calculator skill
