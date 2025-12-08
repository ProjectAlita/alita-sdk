# AI-Native Test Framework

This directory contains the AI-native test framework for automated testing of ALITA SDK toolkits and agents. It works together with agent definitions and toolkit configs stored under `.alita/`.

## Directory Structure

```
.github/ai_native/
├── testcases/            # Test case definitions organized by toolkit
│   ├── ado/              # ADO test cases (TC-*.md)
│   ├── confluence/       # Confluence test cases (TC-*.md)
│   ├── github/           # GitHub test cases (TC-*.md)
│   └── indexer/          # Indexer test cases
└── results/              # Test execution results (generated)
  └── test_execution_summary.json  # Overall summary (matrix/CI)

.alita/
├── agents/
│   ├── test-runner.agent.md         # Test runner agent
│   └── test-data-generator.agent.md # Optional data generator agent
└── tool_configs/                    # Toolkit configuration files
  ├── git-config.json              # GitHub toolkit config
  ├── confluence-config.json       # Confluence toolkit config
  └── ado-config.json              # Azure DevOps toolkit config
```

## Test Case Format

Test cases are written in Markdown format following this structure:

### Example Test Case (TC-001_list_branches.md)

```markdown
# List Branches Displays Custom Branch

## Objective

Verify that the `list_branches_in_repo` tool correctly lists all branches in the repository and that the output includes the branch named `hello`.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Repository** | `VladVariushkin/agent` | Target GitHub repository (owner/repo format) |
| **Access Token** | `GIT_TOOL_ACCESS_TOKEN` | GitHub personal access token for authentication |
| **Base URL** | `https://api.github.com` | GitHub API endpoint |
| **Tool** | `list_branches_in_repo` | GitHub tool to execute for listing branches |

## Config

path: .alita\tool_configs\git-config.json

## Pre-requisites

- A test repository is cloned locally and accessible
- The repository contains at least the default branch (e.g., `main`) and a branch named `hello`
- The testing environment has the necessary permissions and network access to run the tool
- Valid GitHub access token with appropriate permissions for the target repository

## Test Steps & Expectations

### Step 1: Execute the Tool

Execute the `list_branches_in_repo` tool against the target repository.

**Expectation:** The tool runs without errors and returns a textual list of branch names.

### Step 2: Verify Output

Review the tool's output for the presence of branch names.

**Expectation:** The output text contains the branch name `hello`.

## Final Result

- ✅ **Pass:** If all expectations are met throughout the test steps, the objective is achieved and the test passes
- ❌ **Fail:** If any expectation fails at any point, the test fails
```

## Key Components

### Config Section

The config section specifies the toolkit configuration file to use. Configs are stored under `.alita/tool_configs/`.

```markdown
## Config

path: .alita\tool_configs\git-config.json
```

This file contains the toolkit settings including the toolkit type, authentication credentials, repository details, and the list of selected tools that the test can use.

Example configuration file structure:

```json
{
  "type": "github",
  "toolkit_name": "github",
  "github_configuration": {
    "access_token": "${GIT_TOOL_ACCESS_TOKEN}"
  },
  "repository": "VladVariushkin/agent",
  "active_branch": "main",
  "base_branch": "main",
  "selected_tools": [
    "list_branches_in_repo",
    "get_issues",
    "create_file",
    "read_file"
  ]
}
```

### Test Steps

Each step has:
- **Title**: Brief description of the step
- **Instruction**: What the agent should do
- **Expectation**: How to validate the output

Common expectation patterns:
- `"contains the text 'value'"` - Checks if output contains specific text
- `"runs without errors"` - Checks if execution completed successfully

## Running Tests

### Execute All Test Cases in a Directory

```bash
alita agent execute-test-cases \
  .alita/agents/test-runner.agent.md \
  --test-cases-dir .github/ai_native/testcases \
  --results-dir .github/ai_native/results \
  --data-generator .alita/agents/test-data-generator.agent.md \
  --dir .
```

### Execute Specific Toolkit Tests

```bash
# GitHub tests
alita agent execute-test-cases \
  .alita/agents/test-runner.agent.md \
  --test-cases-dir .github/ai_native/testcases/github \
  --results-dir .github/ai_native/results \
  --data-generator .alita/agents/test-data-generator.agent.md \
  --dir .

# Confluence tests
alita agent execute-test-cases \
  .alita/agents/test-runner.agent.md \
  --test-cases-dir .github/ai_native/testcases/confluence \
  --results-dir .github/ai_native/results \
  --data-generator .alita/agents/test-data-generator.agent.md \
  --dir .

# ADO tests
alita agent execute-test-cases \
  .alita/agents/test-runner.agent.md \
  --test-cases-dir .github/ai_native/testcases/ado \
  --results-dir .github/ai_native/results \
  --data-generator .alita/agents/test-data-generator.agent.md \
  --dir .
```
### Execute Specific Test Case Files

```bash
# Run a single test case file by name (can repeat --test-case)
alita agent execute-test-cases \
  .alita/agents/test-runner.agent.md \
  --test-cases-dir .github/ai_native/testcases/github \
  --results-dir .github/ai_native/results \
  --data-generator .alita/agents/test-data-generator.agent.md \
  --dir . \
  --test-case TC-011_read_file.md \
  --test-case TC-010_create_file.md
```

### Skip Data Generation and Override Model

```bash
alita agent execute-test-cases \
  .alita/agents/test-runner.agent.md \
  --test-cases-dir .github/ai_native/testcases/github \
  --results-dir .github/ai_native/results \
  --skip-data-generation \
  --model gpt-4o \
  --temperature 0.0 \
  --max-tokens 2000 \
  --dir .
```


```bash
# Test a specific tool directly
alita toolkit test github \
  --tool list_branches_in_repo \
  --config .alita/tool_configs/git-config.json

# Test with parameters
alita toolkit test confluence \
  --tool get_page_tree \
  --config .alita/tool_configs/confluence-config.json \

## Test Results

### Individual Test Results

```json
{
  "test_case": "List Branches Displays Custom Branch",
  "test_file": "TC-001_list_branches_tool.md",
  "timestamp": "2025-12-04T11:54:43.022632",
  "agent": "Test Runner Agent",
  "objective": "Verify that the list_branches_in_repo tool correctly lists all branches...",
  "config_path": ".github\\ai_native\\testcases\\github\\configs\\git-config.json",
  "passed": true,
  "steps": [
    {
      "step_number": 1,
      "step_title": "Execute the Tool",
      "instruction": "Execute the list_branches_in_repo tool...",
      "output": "Here are the branches: main, hello, feature-branch...",
      "error": null,
      "expectation": "The tool runs without errors...",
      "validation_passed": true,
      "validation_details": "Execution completed without errors"
    },
    {
      "step_number": 2,
      "step_title": "Verify Output",
      "instruction": "Review the tool's output for the presence of branch names...",
      "output": "The output contains: main, hello, feature-branch",
      "validation_passed": true,
      "validation_details": "Output contains 'hello'"
    }
  ]
}
```

### Summary Report (test_execution_summary.json)

```json
{
  "timestamp": "2025-12-04T11:54:43.029932",
  "agent": "Test Runner Agent",
  "total_tests": 10,
  "passed": 8,
  "failed": 2,
  "pass_rate": 80.0,
  "test_results": [...]
}
```

## Writing New Test Cases

1. **Choose the appropriate toolkit directory**: Create test case in `testcases/<toolkit_name>/` (e.g., `github`, `ado`, `confluence`)
2. **Create test case file**: Name it `TC-XXX_description.md` following the numbering convention
3. **Create or reuse config file**: Place toolkit config in `testcases/<toolkit_name>/configs/`
4. **Follow the test case format**: Include all required sections (Objective, Config, Pre-requisites, Test Steps, Final Result)
5. **Define clear expectations**: Make assertions specific and measurable
6. **Run the test**: Use the execute-test-cases command to validate

## Available Toolkits

The test framework currently supports the following toolkits:

- **GitHub** (`testcases/github/`) - GitHub API operations, branches, PRs, issues, files
- **Azure DevOps** (`testcases/ado/`) - ADO repositories, branches, PRs, files
- **Confluence** (`testcases/confluence/`) - Confluence pages, search, attachments
## Validation Rules

The test framework uses pattern matching to validate outputs:
  - Validates: Output must include the exact string

- **No errors**: `"runs without errors"` or `"without errors"`
## Best Practices

1. **One Concept Per Test**: Each test case should verify one specific functionality
5. **Descriptive Names**: Use clear, descriptive file names (TC-XXX_what_it_tests.md)
6. **Document Prerequisites**: List all required setup in the Pre-requisites section
7. **Incremental Steps**: Break complex tests into smaller, validatable steps
8. **Environment Variables**: Use environment variable placeholders (e.g., `${GIT_TOOL_ACCESS_TOKEN}`) for sensitive data
The test framework integrates with GitHub Actions for automated testing. The workflow supports:

### Matrix Execution

Tests are automatically selected based on changed files in PRs:

```yaml
# .github/workflows/test-matrix-execution.yml
- When a PR changes files in alita_sdk/tools/github/, only GitHub tests run
- When a PR changes files in alita_sdk/tools/confluence/, only Confluence tests run
- Otherwise, all test suites run
```

### Manual Execution

The `execute-test-cases` command returns a non-zero exit code when any tests fail:

```bash
# In your CI/CD script
alita agent execute-test-cases \
  .alita/agents/test-runner.agent.md \
  --test-cases-dir .github/ai_native/testcases \
  --results-dir .github/ai_native/results \
  --skip-data-generation \
  --dir .

# Exit code 0 = all tests passed
# Exit code 1 = one or more tests failed
```

## Troubleshooting

### Config File Not Found

If you see: `⚠ Warning: Config file not found`

- Check the path in the Config section matches the actual file location
- Ensure the path is relative to the workspace root
- Use the correct path format: `.alita/tool_configs/<config-file>.json`
- Verify the config file exists under `.alita/tool_configs/`

### Tool Not Available

If the agent says: `"I don't have access to the tool"`

- Verify the toolkit config file has the correct `selected_tools` array
- Check that the toolkit type is correctly specified
- Ensure authentication credentials are valid

### Validation Fails

If validation unexpectedly fails:

- Review the actual output in the result JSON file
- Verify your expectation pattern matches the output format
- Consider making the expectation more flexible or specific
