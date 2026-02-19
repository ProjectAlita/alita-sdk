---
name: "Coverage Calculator"
description: "Calculate and update test coverage metrics for ALITA SDK toolkits"
---

# Coverage Calculator Skill

This skill analyzes test coverage for ALITA SDK toolkits by examining source code and test suites. It provides accurate metrics based on actual file system state.

## When to Use This Skill

- Analyzing overall test coverage across all toolkits
- Calculating coverage metrics for specific toolkits
- Updating the test coverage report
- Identifying coverage gaps and prioritization
- Tracking coverage trends over time

## Key Paths

| Path | Purpose |
|------|----------|
| `alita_sdk/tools/` | Toolkit source code (tool definitions) |
| `.alita/tests/test_pipelines/suites/` | Test suites (YAML test cases) |
| `.alita/tests/test_pipelines/test_coverage.md` | Coverage report (output) |
| `alita_sdk/runtime/tools/` | Runtime framework tools (excluded from coverage) |

## Core Procedures

This skill consists of three main procedures. See individual files for detailed instructions:

### 1. Count Tools in Toolkit

See: [count-tools.md](./count-tools.md)

**What**: Extract tool count from `get_available_tools()` method  
**Input**: Toolkit name (e.g., "github", "jira")  
**Output**: List of tool names and total count

### 2. Count Test Cases

See: [count-tests.md](./count-tests.md)

**What**: Count YAML test files in test suite  
**Input**: Test suite name (e.g., "github_toolkit")  
**Output**: Test case count and file list

### 3. Categorize Toolkit

See: [categorize-toolkit.md](./categorize-toolkit.md)

**What**: Determine if toolkit is user-facing or framework utility  
**Input**: Toolkit directory name  
**Output**: Category classification and reasoning

## Coverage Calculation Formulas

### Toolkit-Level Coverage

```
Coverage % = (Tested Tools / Total Tools) × 100
```

- **Tested Tools**: Count of tools with at least one test case
- **Total Tools**: Count from `get_available_tools()` in wrapper

### Overall Coverage

```
Overall Coverage % = (Toolkits with Tests / Total User-Facing Toolkits) × 100
```

- **Toolkits with Tests**: User-facing toolkits that have test suites
- **Total User-Facing Toolkits**: All toolkits excluding framework utilities

## Toolkit Categories

### User-Facing Toolkits (Require Test Coverage)

**Version Control**: github, gitlab, gitlab_org, bitbucket, localgit, ado  
**Issue Tracking**: jira, advanced_jira_mining, rally  
**Documentation**: confluence, sharepoint  
**Test Management**: xray, qtest, testrail, testio, zephyr*, report_portal  
**API Tools**: postman, openapi, custom_open_api  
**Communication**: slack, gmail, yagmail  
**CRM/ITSM**: salesforce, servicenow, keycloak, carrier  
**Data**: sql, pandas, elastic, bigquery, delta_lake  
**Cloud**: aws, azure, gcp, k8s  
**Design**: figma  
**Other**: ocr, pptx, memory, google_places, azure_search

### Framework Utilities (No Tests Required)

**base**: BaseAction class for all toolkits  
**browser**: Browser automation support (empty)  
**chunkers**: Document chunking strategies  
**llm**: LLM integration utilities  
**utils**: Decorators and helper functions  
**vector_adapters**: Vector storage adapters  
**code**: Code analysis utilities (linter, sonar)

## Report Output Format

The coverage report should be updated at:  
`.alita/tests/test_pipelines/test_coverage.md`

**Required Sections**:
1. **Executive Summary**: High-level metrics table
2. **Toolkits With Tests**: Detailed coverage table with status indicators
3. **Toolkits Without Tests**: Organized by priority (Critical/High/Medium/Low)
4. **Framework Utilities**: List with no coverage expectations
5. **Coverage Trend**: Historical data with dates
6. **Recommendations**: Next steps for improving coverage

## Key Principles

✅ **Accuracy**: All counts must match actual files (never estimate)  
✅ **Verification**: Cross-check source code against test suites  
✅ **Separation**: Keep user-facing toolkits separate from framework utilities  
✅ **Traceability**: Document all counting methods  
✅ **Consistency**: Use same methodology every time  
✅ **Timestamp**: Include date on all report updates

## Example Workflow

1. **Scan** `alita_sdk/tools/` for all toolkit directories
2. **Categorize** each toolkit using [categorize-toolkit.md](./categorize-toolkit.md)
3. **Count tools** for each user-facing toolkit using [count-tools.md](./count-tools.md)
4. **Count tests** for each test suite using [count-tests.md](./count-tests.md)
5. **Match** test suites to toolkits (by naming convention)
6. **Calculate** coverage percentages using formulas above
7. **Update** coverage report with new data and timestamp
8. **Append** new data point to coverage trend section

## Success Criteria

- All tool counts derived from actual `get_available_tools()` methods
- All test counts match YAML files on disk
- Coverage percentages are mathematically correct
- Report reflects current state of repository
- Framework utilities clearly separated from user-facing toolkits
- Trend data shows progression over time
