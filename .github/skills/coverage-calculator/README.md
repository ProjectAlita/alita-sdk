# Coverage Calculator Skills

This directory contains VS Code Copilot agent skills for analyzing test coverage in the ALITA SDK.

## Overview

These skills help the **Test Coverage Analyzer** agent (defined in `.github/agents/test-coverage-analyzer.agent.md`) perform systematic test coverage analysis by counting tools, test cases, and categorizing toolkits.

## Skills Structure

### Main Skill: [skill.md](./skill.md)

The master skill file that defines the Coverage Calculator skill. It includes:
- Purpose and usage guidelines
- Key file paths
- Coverage calculation formulas
- Toolkit categorization
- Report format requirements
- Example workflow

### Supporting Procedures

Three specialized procedures that break down the coverage analysis process:

#### 1. [count-tools.md](./count-tools.md)
**Purpose**: Count the number of tools in a toolkit from its `get_available_tools()` method

**Input**: Toolkit name (e.g., "github", "jira")  
**Output**: Tool count, tool list, disabled tools

**Key Steps**:
- Locate toolkit directory in `alita_sdk/tools/`
- Find wrapper file (`api_wrapper.py` or similar)
- Parse `get_available_tools()` method
- Count active (non-commented) tools
- Extract tool names

#### 2. [count-tests.md](./count-tests.md)
**Purpose**: Count the number of test cases in a test suite

**Input**: Test suite name (e.g., "github_toolkit")  
**Output**: Test count, test file list

**Key Steps**:
- Locate suite directory in `.alita/tests/test_pipelines/suites/`
- List files in `tests/` subdirectory
- Filter for `test_case_*.yaml` pattern
- Count matching files (actual count, not estimated)
- Optionally extract test metadata

#### 3. [categorize-toolkit.md](./categorize-toolkit.md)
**Purpose**: Determine if a toolkit is user-facing, framework utility, or container

**Input**: Toolkit directory name  
**Output**: Category classification with reasoning

**Key Steps**:
- Check against known framework utilities
- Inspect directory structure
- Analyze wrapper file
- Check for `get_available_tools()` method
- Classify as user-facing, framework utility, or container

## How VS Code Copilot Uses These Skills

When the Test Coverage Analyzer agent needs to:

1. **Analyze full coverage**: Uses the main [skill.md](./skill.md) workflow
2. **Count tools in a specific toolkit**: References [count-tools.md](./count-tools.md)
3. **Count test cases in a suite**: References [count-tests.md](./count-tests.md)
4. **Classify a new toolkit**: Uses [categorize-toolkit.md](./categorize-toolkit.md)

The agent can invoke these skills through natural language commands like:
- "Analyze test coverage"
- "Count tools in the github toolkit"
- "How many test cases does jira have?"
- "Categorize the new xray toolkit"

## Key Concepts

### User-Facing Toolkits
Toolkits that expose tools for users to interact with external services. These **require test coverage**.

Examples: github, jira, confluence, postman, slack, etc.

### Framework Utilities
Infrastructure components that support toolkit development but don't expose user-facing tools. These **do not require test coverage**.

Examples: base, browser, chunkers, llm, utils, vector_adapters

### Coverage Metrics

**Toolkit Coverage**:
```
Coverage % = (Tested Tools / Total Tools) × 100
```

**Overall Coverage**:
```
Overall Coverage % = (Toolkits with Tests / Total User-Facing Toolkits) × 100
```

## File Paths Reference

| Path | Purpose |
|------|----------|
| `alita_sdk/tools/` | Toolkit source code |
| `alita_sdk/tools/{toolkit}/api_wrapper.py` | Tool definitions |
| `.alita/tests/test_pipelines/suites/` | Test suites |
| `.alita/tests/test_pipelines/suites/{suite}/tests/` | Test case YAML files |
| `.alita/tests/test_pipelines/test_coverage.md` | Coverage report output |

## Skills Best Practices

### Accuracy Over Speed
- Always count actual files (never estimate)
- Verify tool counts against source code
- Cross-check test counts with file system

### Clear Documentation
- Document all counting methods
- Explain categorization decisions
- Include timestamps on reports

### Separation of Concerns
- Keep user-facing toolkits separate from framework utilities
- Only include user-facing toolkits in coverage metrics
- Document framework utilities separately

### Consistency
- Use the same methodology every time
- Follow the same workflow for each analysis
- Maintain historical trend data

## Related Documentation

- **Agent Definition**: `.github/agents/test-coverage-analyzer.agent.md`
- **Test Framework**: `.alita/tests/test_pipelines/README.md`
- **Coverage Report**: `.alita/tests/test_pipelines/test_coverage.md`
- **VS Code Copilot Skills**: https://code.visualstudio.com/docs/copilot/customization/agent-skills

## Usage Examples

### Example 1: Full Coverage Analysis

**Command**: "Analyze test coverage and update the report"

**Process**:
1. Uses [skill.md](./skill.md) workflow
2. Scans all toolkit directories
3. Applies [categorize-toolkit.md](./categorize-toolkit.md) to each
4. Uses [count-tools.md](./count-tools.md) for user-facing toolkits
5. Uses [count-tests.md](./count-tests.md) for test suites
6. Calculates coverage percentages
7. Updates test_coverage.md with results

### Example 2: Single Toolkit Analysis

**Command**: "Show coverage details for postman toolkit"

**Process**:
1. Uses [count-tools.md](./count-tools.md) on `alita_sdk/tools/postman/`
2. Uses [count-tests.md](./count-tests.md) on `.alita/tests/test_pipelines/suites/postman_toolkit/`
3. Calculates coverage percentage
4. Identifies which tools are tested/untested

### Example 3: New Toolkit Integration

**Command**: "Add xray toolkit to coverage tracking"

**Process**:
1. Uses [categorize-toolkit.md](./categorize-toolkit.md) to verify it's user-facing
2. Uses [count-tools.md](./count-tools.md) to count available tools
3. Checks if test suite exists using [count-tests.md](./count-tests.md)
4. Adds to coverage report in appropriate section

## Contributing

When updating these skills:

1. Maintain YAML frontmatter format (`name`, `description`)
2. Keep procedures clear and step-by-step
3. Include examples and common patterns
4. Update cross-references between files
5. Test with actual toolkit/test data
6. Verify compatibility with Test Coverage Analyzer agent

## Version History

- **2025-02-18**: Upgraded to VS Code Copilot agent skills format
  - Added proper YAML frontmatter
  - Enhanced with detailed procedures
  - Improved cross-references
  - Added comprehensive examples
  - Aligned with VS Code documentation standards
