---
description: Test coverage report structure and formatting guidelines for ALITA SDK
applyTo: ".alita/tests/test_pipelines/test_coverage.md"
---

# Test Coverage Report Structure

This document defines the required structure and formatting for the ALITA SDK test coverage report located at `.alita/tests/test_pipelines/test_coverage.md`.

## Report Location

**File**: `.alita/tests/test_pipelines/test_coverage.md`

**Update Frequency**: On-demand via Test Coverage Analyzer agent

## Required Sections (in order)

### 1. Header & Timestamp

```markdown
# ALITA SDK Test Coverage Analysis

Generated on: YYYY-MM-DD
```

**Rules**:
- Use ISO date format (YYYY-MM-DD)
- Update timestamp on every report update
- Keep title consistent

### 2. Executive Summary

```markdown
## Executive Summary

| Metric | Value |
|--------|-------|
| **User-Facing Toolkits** | <count> |
| **Framework Utilities** | <count> |
| **Toolkits with Test Coverage** | <count> |
| **Toolkits WITHOUT Tests** | <count> |
| **Overall Toolkit Coverage** | **<percent>%** (<with>/<total>) |
| **Tools Tested** | ~<count> out of ~<total> |
| **Total Test Cases** | <count> |
| **Framework Test Suites** | <count> (<names>) |
```

**Rules**:
- All counts must be accurate (derived from actual files)
- Overall Toolkit Coverage is bold and includes ratio
- Tools Tested may use `~` for approximate counts if exact mapping unclear
- Framework Test Suites lists non-toolkit tests (e.g., State Retrieval, Structured Output)

**Calculation Formulas**:
```
Overall Toolkit Coverage % = (Toolkits with Tests / User-Facing Toolkits) × 100
```

### 3. Test Coverage by Toolkit Table

```markdown
## Test Coverage by Toolkit (<count> Toolkits with Tests)

| Toolkit | Total Tools | Tested Tools | Coverage % | Test Cases | Status |
|---------|-------------|--------------|------------|------------|--------|
| **<name>** | <total> | <tested> | **<percent>%** | <tests> | <status> |
```

**Rules**:
- One row per toolkit with test coverage
- Sort by coverage % (descending), then by toolkit name (alphabetical)
- Toolkit name in bold
- Coverage % in bold
- Use status indicators (see Status Indicators section below)
- Mark NEW toolkits with ✅ **NEW** suffix in Status column
- Include comprehensive notes for 100% coverage toolkits

**Subsection: Framework Test Suites**

```markdown
### Framework Test Suites (Pipeline Testing)

| Suite | Test Cases | Purpose |
|-------|------------|---------|
| **State Retrieval** | <count> | Purpose description |
| **Structured Output** | <count> | Purpose description |
```

### 4. Toolkits WITHOUT Test Coverage

```markdown
## Toolkits WITHOUT Test Coverage (<count> toolkits)
```

**Organize by Priority**:

```markdown
### 🚨 Critical Priority
| Toolkit | Location | Total Tools | Notes |
|---------|----------|-------------|-------|
| **<name>** | `tools/<path>/` | <count> | Description |

### 🔶 High Priority
| Toolkit | Location | Total Tools | Notes |
|---------|----------|-------------|-------|

### 🔷 Medium Priority
| Toolkit | Location | Total Tools | Notes |
|---------|----------|-------------|-------|

### ⬜ Low Priority
| Toolkit | Location | Total Tools | Notes |
|---------|----------|-------------|-------|
```

**Priority Classifications**:

| Priority | Emoji | Criteria |
|----------|-------|----------|
| **Critical** | 🚨 | High-impact, frequently used in production (GitLab Org, TestRail, TestIO, Carrier) |
| **High** | 🔶 | Commonly used, important integrations (Slack, ServiceNow, Zephyr variants) |
| **Medium** | 🔷 | Standard toolkits, moderate usage (LocalGit, SharePoint, Pandas, SQL, Memory, ReportPortal, Rally) |
| **Low** | ⬜ | Specialized, niche, or low-usage toolkits (OCR, Email, Cloud providers) |

### 5. Framework Utilities Section

```markdown
## Framework Utilities (No Tests Required)

These are infrastructure components that support toolkits but don't expose user-facing tools:

| Utility | Location | Purpose |
|---------|----------|---------|
| **base** | `tools/base/` | BaseAction class inherited by all toolkits |
| **browser** | `tools/browser/` | Browser automation support (empty) |
| **chunkers** | `tools/chunkers/` | Document chunking strategies |
| **llm** | `tools/llm/` | LLM integration utilities |
| **utils** | `tools/utils/` | Decorators and helper functions |
| **vector_adapters** | `tools/vector_adapters/` | Vector storage adapters |
```

**Rules**:
- List all framework utilities
- Explain why they don't require tests
- Keep consistent with categorization in skills

### 6. Detailed Coverage Analysis by Toolkit

```markdown
## Detailed Coverage Analysis by Toolkit

### 🟢 Complete Coverage (100%)

#### <Toolkit> Toolkit (100% - <tested>/<total> tools)
**Location**: `alita_sdk/tools/<toolkit>/api_wrapper.py`

| Tool Name | Tested | Test Case(s) |
|-----------|--------|--------------|
| `<tool_name>` | ✅ | test_case_XX |
| `<tool_name>` | ❌ | - |

**Notes**: <observations about coverage, special features, disabled tools>

### 🟢 Excellent Coverage (90%+)

#### <Toolkit> Toolkit (<percent>% - <tested>/<total> tools)
...

### 🟢 Good Coverage (80-89%)

### 🟡 Needs Improvement (50-79%)
```

**Coverage Groupings**:
- **🟢 Complete** (100%)
- **🟢 Excellent** (90-99%)
- **🟢 Good** (80-89%)
- **🟡 Needs Improvement** (50-79%)
- **🔴 Critical** (<50%)

**Rules**:
- Group toolkits by coverage tier
- Within each tier, sort by coverage % (desc)
- Include tool-by-tool breakdown for each toolkit
- Note disabled/commented tools
- Highlight special test scenarios (negative tests, integration tests)

### 7. Framework Test Suites Detail

```markdown
## Framework Test Suites

### <Suite Name> Suite (<count> tests)
Tests <purpose>:
- Feature 1
- Feature 2
- ...
```

**Rules**:
- One subsection per framework suite
- List what each suite tests
- Include test count

### 8. Recommendations Section

```markdown
## Recommendations

### ✅ Recent Progress (YYYY-MM-DD)

**New Test Suites Added:**
- **<Toolkit>** - <percent>% coverage (<tested>/<total> tools, <count> tests) ✅ **NEW**

**Coverage Improvements:**
- **<Toolkit>**: <old>% → <new>%

Test cases increased by **X%** (old → new) since <date>.

### 🚨 Priority 1: Critical - New Toolkit Coverage

1. **<Toolkit> Toolkit** (0% coverage, <count> tools)
   - Use case description
   - Recommended test focus

### 📌 Priority 2: Improve Existing Coverage

1. **<Toolkit>** (<current>% → <target>%)
   - Add tests for: <tool>, <tool>, <tool>
   - Priority: <reason>

### 💡 Priority 3: Nice to Have

1. **<Category>**: <toolkit>, <toolkit>
```

**Rules**:
- Always show recent progress with date
- List new test suites with NEW marker
- Prioritize recommendations (Critical → High → Nice to Have)
- Include specific tool names to test
- Provide rationale for priorities

### 9. Test Quality Metrics (Optional)

```markdown
## Test Quality Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Toolkits with tests | <percent>% (<count>/<total>) | 50%+ |
| Average tools tested per toolkit | ~<percent>% | 80%+ |
| Test cases with negative scenarios | ~<percent>% | 50% |
| Integration tests | ~<percent>% | 15% |
```

### 10. Coverage Trend

```markdown
## Coverage Trend

| Date | Toolkits Covered | Tools Tested | Test Cases |
|------|------------------|--------------|------------|
| YYYY-MM-DD | <count> | <count> | <count> |
| YYYY-MM-DD | <count> | <count> | <count> |
```

**Rules**:
- NEVER delete historical data
- ALWAYS append new rows (descending by date)
- Include date, toolkit count, tools count, test count
- Add note about significant changes

**Latest Update Line**:
```markdown
**Latest Update**: <Description of changes>
```

### 11. Footer Note

```markdown
---

*Note: This analysis is based on test files in `.alita/tests/test_pipelines/suites/` and tool implementations in `alita_sdk/tools/` and `alita_sdk/runtime/tools/`*
```

## Status Indicators

### Coverage Status Badges

| Coverage % | Status | Indicator |
|------------|--------|-----------|
| 100% | Complete | 🟢 Complete |
| 90-99% | Excellent | 🟢 Excellent |
| 80-89% | Good | 🟢 Good |
| 50-79% | Needs Work | 🟡 Needs Work |
| <50% | Critical | 🔴 Critical |

**Usage in Tables**:
- Use emoji + text for Status column
- Add ✅ for new additions
- Add ⭐ for noteworthy achievements

### Tool Testing Status

| Symbol | Meaning |
|--------|---------|
| ✅ | Tool is tested |
| ❌ | Tool is not tested |
| ⚠️ | Tool is indirectly tested |

### Change Indicators

| Symbol | Meaning |
|--------|---------|
| 🆕 | New toolkit/feature |
| 📈 | Coverage improved |
| 📉 | Coverage decreased |
| ✅ | Completed/achieved |

## Formatting Rules

### Text Formatting

- **Bold**: Toolkit names, coverage percentages, section headers
- `Code`: Tool names, file paths, code elements
- *Italic*: Optional or conditional information

### Numbers

- **Exact counts**: When counting actual files (test cases, toolkits)
- **Approximate counts** (~): When exact tool-to-test mapping unclear
- **Percentages**: Always show as `XX%` with percent sign
- **Ratios**: Show as `(numerator/denominator)` in parentheses

### Paths

- **Toolkit source**: `` `alita_sdk/tools/<toolkit>/api_wrapper.py` ``
- **Test suites**: `` `.alita/tests/test_pipelines/suites/<suite>/tests/` ``
- **Coverage report**: `` `.alita/tests/test_pipelines/test_coverage.md` ``

Always use backticks for paths and forward slashes (even on Windows).

### Tables

- **Headers**: Use `**bold**` for column headers
- **Alignment**: Left-align text, right-align numbers where appropriate
- **Spacing**: One space after `|` delimiter
- **Blank cells**: Use `-` for empty cells in data columns

### Links

Use relative paths for internal references:
```markdown
[skill.md](../skills/coverage-calculator/skill.md)
```

## Data Integrity Rules

### Counting Rules

1. **Tool Count**: Count non-commented tools from `get_available_tools()` method
2. **Test Count**: Count `test_case_*.yaml` files in suite's `tests/` directory
3. **Toolkit Count**: Count directories in `alita_sdk/tools/` with wrappers (excluding framework utilities)
4. **Coverage Calculation**: `(Tested Tools / Total Tools) × 100`

### Verification Checklist

Before publishing report:
- [ ] All counts match actual files on disk
- [ ] All percentages calculated correctly
- [ ] Historical trend data preserved
- [ ] Timestamp updated
- [ ] New toolkits marked with ✅ **NEW**
- [ ] Status indicators match coverage percentages
- [ ] Framework utilities separated from user-facing toolkits
- [ ] Recommendations reflect current gaps

### Historical Data Preservation

**NEVER**:
- Delete rows from Coverage Trend table
- Remove historical dates
- Overwrite previous metrics

**ALWAYS**:
- Append new data to trend table
- Keep previous report sections for reference
- Note what changed since last update

## Update Workflow

When updating the report:

1. **Read Current Report**: Get baseline metrics from previous version
2. **Scan File System**: Count tools and tests from actual files
3. **Calculate Metrics**: Apply formulas from Coverage Calculator skill
4. **Update Sections**: Modify each section in order
5. **Append Trend Data**: Add new row to Coverage Trend table
6. **Update Recommendations**: Highlight what changed
7. **Verify Accuracy**: Check all counts and calculations
8. **Update Timestamp**: Set "Generated on" date

## Examples

### Example: New Toolkit Entry

```markdown
| **Postman** | 31 | 31 | **100%** | 57 | 🟢 Complete ✅ **NEW** |
```

### Example: Coverage Improvement

```markdown
**Coverage Improvements:**
- **GitHub**: 42% → 58% (+16%)
- **Zephyr Essential**: Added 24 tests (0% → 47%)
```

### Example: Detailed Tool Breakdown

```markdown
#### Postman Toolkit (100% - 31/31 tools) ✅
**Location**: `alita_sdk/tools/postman/api_wrapper.py`

| Tool Name | Tested | Test Case(s) |
|-----------|--------|--------------|
| `get_collections` | ✅ | test_case_01 |
| `get_collection` | ✅ | test_case_05 |
| `create_folder` | ✅ | test_case_28, test_case_29 |

**Notes**: Complete 100% coverage with comprehensive testing including happy path and edge cases (invalid paths, special characters, clearing values). Largest test suite with 57 test cases.
```

## Common Mistakes to Avoid

1. ❌ Using estimated tool counts instead of actual counts
2. ❌ Deleting historical trend data
3. ❌ Forgetting to update timestamp
4. ❌ Including framework utilities in toolkit count
5. ❌ Mixing up "Tools Tested" vs "Test Cases" counts
6. ❌ Incorrect coverage percentage calculations
7. ❌ Not marking new toolkits with ✅ **NEW**
8. ❌ Forgetting to separate completed, excellent, good, and critical coverage tiers

## Notes

- This structure is based on the current report at `.alita/tests/test_pipelines/test_coverage.md`
- The Test Coverage Analyzer agent uses this structure when updating the report
- The Coverage Calculator skill provides the detailed procedures for counting and calculation
- All formatting should remain consistent across updates for readability and maintainability
