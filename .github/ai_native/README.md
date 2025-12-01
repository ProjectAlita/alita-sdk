# AI-Native Test Framework

This directory contains the AI-native test framework for automated testing of ALITA SDK toolkits and agents.

## Directory Structure

```
.github/ai_native/
├── testcases/           # Test case definitions
│   ├── configs/         # Toolkit configuration files for tests
│   └── TC-*.md          # Individual test case files
└── results/             # Test execution results (generated)
    ├── TC-*_result.json # Individual test results
    └── summary.json     # Overall test summary
```

## Test Case Format

Test cases are written in Markdown format following this structure:

### Example Test Case (TC-001_list_branches_tool.md)

```markdown
# Test Case Title

## Objective

Brief description of what the test verifies.

## Test Data Configuration

### Toolkit Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Setting** | `value` | Description |

## Config

path: .github\ai_native\testcases\configs\TC-001_config.json

## Pre-requisites

- List of prerequisites
- Environment setup requirements

## Test Steps & Expectations

### Step 1: Action Title

Action description or instruction to the agent.

**Expectation:** What should happen when the step executes successfully.

### Step 2: Validation Title

Validation description or instruction.

**Expectation:** Specific assertion (e.g., "The output contains the text 'expected_value'").

## Final Result

- ✅ **Pass:** Conditions for test to pass
- ❌ **Fail:** Conditions for test to fail
```

## Key Components

### Config Section

The config section specifies the toolkit configuration file to use:

```markdown
## Config

path: .github\ai_native\testcases\configs\TC-001_git-config.json
```

This file contains the toolkit settings (e.g., API tokens, repository URLs, selected tools).

### Test Steps

Each step has:
- **Title**: Brief description of the step
- **Instruction**: What the agent should do
- **Expectation**: How to validate the output

Common expectation patterns:
- `"contains the text 'value'"` - Checks if output contains specific text
- `"runs without errors"` - Checks if execution completed successfully

## Running Tests

### Execute All Test Cases

```bash
alita-cli agent execute-test-cases \
    .github/agents/test-runner.agent.json \
    .github/ai_native/testcases \
    .github/ai_native/results
```

### With Custom Settings

```bash
alita-cli agent execute-test-cases \
    .github/agents/test-runner.agent.json \
    .github/ai_native/testcases \
    .github/ai_native/results \
    --model gpt-4o \
    --temperature 0.0
```

### Command Options

- `--model TEXT`: Override LLM model
- `--temperature FLOAT`: Override temperature
- `--max-tokens INTEGER`: Override max tokens
- `--dir DIRECTORY`: Grant agent filesystem access to directory

## Test Results

After execution, results are saved in the specified results directory:

### Individual Test Results (TC-001_list_branches_tool_result.json)

```json
{
  "test_case": "List Branches Displays Custom Branch",
  "test_file": "TC-001_list_branches_tool.md",
  "timestamp": "2025-11-28T11:54:43.022632",
  "agent": "Test Runner Agent",
  "objective": "Verify that the list_branches_in_repo tool...",
  "config_path": ".github\\ai_native\\testcases\\configs\\TC-001_git-config.json",
  "passed": false,
  "steps": [
    {
      "step_number": 1,
      "step_title": "Execute the Tool",
      "instruction": "Execute the list_branches_in_repo tool...",
      "output": "Here are the branches...",
      "error": null,
      "expectation": "The tool runs without errors...",
      "validation_passed": true,
      "validation_details": "Execution completed without errors"
    }
  ]
}
```

### Summary Report (summary.json)

```json
{
  "timestamp": "2025-11-28T11:54:43.029932",
  "agent": "Test Runner Agent",
  "total_tests": 1,
  "passed": 0,
  "failed": 1,
  "pass_rate": 0.0,
  "test_results": [...]
}
```

## Writing New Test Cases

1. Create a new file: `TC-XXX_description.md` in the testcases directory
2. Follow the test case format above
3. Create a toolkit config file in `testcases/configs/` if needed
4. Reference the config in the test case's Config section
5. Define clear test steps with specific expectations
6. Run the test using the execute-test-cases command

## Validation Rules

The test framework uses pattern matching to validate outputs:

- **Contains text**: `"contains 'text'"` or `"contains \"text\""`
  - Example: `"The output contains the text 'my_test_branch'"`
  - Validates: Output must include the exact string

- **No errors**: `"runs without errors"` or `"without errors"`
  - Validates: No error keywords in output (error, exception, failed, traceback)

- **Default**: If output is generated, step passes
  - Use for exploratory or information-gathering steps

## Best Practices

1. **One Concept Per Test**: Each test case should verify one specific functionality
2. **Clear Expectations**: Make assertions specific and measurable
3. **Isolated Configs**: Each test should have its own config file to avoid conflicts
4. **Descriptive Names**: Use clear, descriptive file names (TC-XXX_what_it_tests.md)
5. **Document Prerequisites**: List all required setup in the Pre-requisites section
6. **Incremental Steps**: Break complex tests into smaller, validatable steps

## CI/CD Integration

The execute-test-cases command returns a non-zero exit code when tests fail, making it suitable for CI/CD pipelines:

```bash
# In your CI/CD script
alita-cli agent execute-test-cases \
    .github/agents/test-runner.agent.json \
    .github/ai_native/testcases \
    .github/ai_native/results

# Exit code 0 = all tests passed
# Exit code 1 = one or more tests failed
```

## Troubleshooting

### Config File Not Found

If you see: `⚠ Warning: Config file not found`

- Check the path in the Config section
- Ensure the path is relative to the workspace root
- Use forward slashes (/) or backslashes (\\) consistently

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
