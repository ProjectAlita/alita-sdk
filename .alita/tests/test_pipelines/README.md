# Pipeline Test Framework

Execute and validate toolkit test pipelines on the Elitea platform.

## Quick Start

```bash
# Set environment variables (or use .env file in elitea root)
export AUTH_TOKEN="your_api_key"
export BASE_URL="http://192.168.68.115"
export PROJECT_ID="2"
export GIT_TOOL_ACCESS_TOKEN="ghp_xxx"

# Full workflow (4 steps)
python setup.py github_toolkit -v -o .env.generated       # 1. Create toolkit, branches, config
python seed_pipelines.py github_toolkit --env-file .env.generated  # 2. Deploy test pipelines
python run_suite.py github_toolkit --env-file .env.generated       # 3. Execute tests
python cleanup.py github_toolkit --env-file .env.generated -y      # 4. Remove test artifacts
```

### Manual Workflow (if toolkit already exists)

```bash
# Set toolkit ID if already created
export GITHUB_TOOLKIT_ID="71"
export GITHUB_TOOLKIT_NAME="testing"

# Seed and run
python seed_pipelines.py github_toolkit
python run_suite.py github_toolkit
python run_pipeline.py --name "GH1 - List Branches"
```

---

## Workflow Overview

```
┌─────────────┐     ┌──────────────┐     ┌───────────┐     ┌─────────────┐
│  setup.py   │────▶│ seed_pipe... │────▶│ run_suite │────▶│ cleanup.py  │
│  (prepare)  │     │   (deploy)   │     │  (execute)│     │  (teardown) │
└─────────────┘     └──────────────┘     └───────────┘     └─────────────┘
     │                                                            │
     ▼                                                            ▼
  Creates:                                                    Removes:
  - Toolkits                                                 - Test branches
  - Branches                                                 - Test PRs
  - Test issues                                              - Test files
  - Configurations                                           - Pipelines
  - Env vars (.env.generated)                                - Toolkits
```

### config.yaml Structure

Each test suite has a `config.yaml` that defines setup and cleanup steps:

```yaml
name: github_toolkit
description: GitHub toolkit integration tests

# Setup steps - executed before tests
setup:
  - name: Create GitHub Toolkit
    type: toolkit
    action: create_or_update
    config:
      config_file: ../../../tool_configs/git-config.json
      overrides:
        github_configuration:
          private: true
          alita_title: github  # References a configuration
    save_to_env:
      - key: GITHUB_TOOLKIT_ID
        value: $.id

  - name: Create Test Branch
    type: github
    action: create_branch
    config:
      toolkit_ref: ${GITHUB_TOOLKIT_ID}
      branch_name: tc-test-${TIMESTAMP}

# Cleanup steps - executed after tests
cleanup:
  - name: Delete Test Branches
    type: github
    action: delete_branches
    config:
      pattern: "tc-test-*"
    continue_on_error: true

  - name: Delete Test Pipelines
    type: pipeline
    action: delete
    config:
      pattern: "GH*"
```

---

## Scripts Reference

### setup.py

Prepare test environment from config.yaml. Creates toolkits, branches, configurations, and issues.

```bash
python setup.py <folder> [options]

Options:
  --base-url URL        Platform URL
  --project-id ID       Target project
  --env-file FILE       Load env vars from file
  --dry-run             Preview without executing
  --output-env, -o FILE Write generated env vars to file
  -v, --verbose         Detailed output
  --json                JSON output

Examples:
  python setup.py github_toolkit
  python setup.py github_toolkit --dry-run -v
  python setup.py github_toolkit -o .env.generated
```

### seed_pipelines.py

Deploy YAML test case files to platform as pipelines:

```bash
python seed_pipelines.py <folder> [options]

Options:
  --base-url URL          Platform URL
  --project-id ID         Target project
  --github-toolkit-id ID  Toolkit ID for substitution
  --env-file FILE         Load env vars from file
  --dry-run               Preview without creating
  -v, --verbose           Detailed output

Examples:
  python seed_pipelines.py github_toolkit
  python seed_pipelines.py github_toolkit --env-file .env.generated
```

### run_suite.py

Execute multiple pipelines and report results:

```bash
python run_suite.py <folder> [options]
python run_suite.py --pattern "GH*" [options]

Options:
  <folder>              Run pipelines from folder's YAML files
  --pattern PATTERN     Name pattern (repeatable)
  --ids ID [ID ...]     Specific pipeline IDs
  --env-file FILE       Load env vars from file
  --parallel N          Parallel execution count
  --timeout SECONDS     Per-pipeline timeout (default: 120)
  --fail-fast           Stop on first failure
  --json                JSON output
  -v, --verbose         Detailed output
  --exit-code           Exit 0=all pass, 1=failures

Examples:
  python run_suite.py github_toolkit --env-file .env.generated
  python run_suite.py --pattern "GH*" --parallel 4
  python run_suite.py --ids 267 268 269
```

### cleanup.py

Remove test artifacts after tests:

```bash
python cleanup.py <folder> [options]

Options:
  --base-url URL        Platform URL
  --project-id ID       Target project
  --env-file FILE       Load env vars from file
  --dry-run             Preview without executing
  --skip-pipelines      Don't delete pipelines
  --skip-github         Don't cleanup GitHub artifacts
  --skip-toolkit        Don't delete toolkit
  --yes, -y             Skip confirmation
  -v, --verbose         Detailed output
  --json                JSON output

Examples:
  python cleanup.py github_toolkit --env-file .env.generated -y
  python cleanup.py github_toolkit --dry-run
  python cleanup.py github_toolkit --skip-toolkit -y
```

### run_pipeline.py

Execute a single pipeline:

```bash
python run_pipeline.py <id> [options]
python run_pipeline.py --name "Pipeline Name" [options]

Options:
  --json                  JSON output
  --exit-code             Exit 0=pass, 1=fail
  -v, --verbose           Detailed output
  --timeout SECONDS       Execution timeout
```

### delete_pipelines.py

Remove pipelines:

```bash
python delete_pipelines.py [options]

Options:
  --list                  List all pipelines
  --ids ID [ID ...]       Delete specific IDs
  --range START-END       Delete ID range
  --pattern TEXT          Delete by name pattern
  --dry-run               Preview without deleting
  --yes                   Skip confirmation
```

---

## Environment Variables

```bash
# Authentication (one required)
AUTH_TOKEN=your_api_key
ELITEA_TOKEN=your_api_key
API_KEY=your_api_key

# Platform
BASE_URL=http://192.168.68.115
DEPLOYMENT_URL=http://192.168.68.115
PROJECT_ID=2

# Toolkit (set manually or generated by setup.py)
GITHUB_TOOLKIT_ID=71
GITHUB_TOOLKIT_NAME=testing
GIT_TOOL_ACCESS_TOKEN=ghp_xxx
```

---

## Using --env-file for Isolated Environments

The `--env-file` option allows you to use a specific environment file. This is useful for:

- **CI/CD pipelines**: Use different configs for different environments
- **Parallel test runs**: Each run uses its own generated environment
- **Avoiding conflicts**: Don't pollute the main `.env` file

```bash
# Setup generates .env.generated with toolkit IDs, branch names, etc.
python setup.py github_toolkit -o .env.generated

# All subsequent commands use the generated env file
python seed_pipelines.py github_toolkit --env-file .env.generated
python run_suite.py github_toolkit --env-file .env.generated
python cleanup.py github_toolkit --env-file .env.generated -y
```

**Priority order for environment variables:**
1. Custom env file (from `--env-file`)
2. OS environment variables
3. Default `.env` file locations

---

## Full Automation Example

```bash
#!/bin/bash
# run_github_tests.sh - Full automated test run

set -e

cd alita-sdk/.alita/tests/test_pipelines

echo "=== Setting up test environment ==="
python setup.py github_toolkit -v -o .env.generated

echo "=== Deploying test pipelines ==="
python seed_pipelines.py github_toolkit --env-file .env.generated

echo "=== Running tests ==="
python run_suite.py github_toolkit --env-file .env.generated --json > results.json

echo "=== Cleaning up ==="
python cleanup.py github_toolkit --env-file .env.generated -y

echo "=== Done ==="
cat results.json
```

---

## Pipeline YAML Specification

This section defines the rules for creating pipeline YAML files. **AI agents must follow these rules exactly.**

### File Structure

```yaml
name: "TC1 - Test Name"                    # REQUIRED: Unique name with prefix
description: "What this test validates"    # REQUIRED: Clear description

toolkits:                                  # OPTIONAL: External toolkits used
  - id: ${GITHUB_TOOLKIT_ID}
    name: ${GITHUB_TOOLKIT_NAME}

state:                                     # REQUIRED: All state variables
  input:
    type: str
  messages:
    type: list
  # ... other variables

entry_point: first_node_id                 # REQUIRED: Starting node ID

nodes:                                     # REQUIRED: List of execution nodes
  - id: node_id
    type: code|toolkit|llm
    # ... node-specific fields
    transition: next_node_id|END
```

### State Variables

**Rules:**
1. Every variable used in the pipeline MUST be declared in `state:`
2. Variables are accessed via `alita_state.get('variable_name')`
3. Default values can be set with `value:` field

**Supported Types:**
```yaml
state:
  my_string:
    type: str
    value: "default value"        # Optional default
  my_number:
    type: int
    value: 42
  my_float:
    type: float
  my_bool:
    type: bool
    value: true
  my_list:
    type: list
    value: []                     # Empty list default
  my_dict:
    type: dict
    value: {}                     # Empty dict default
```

### Node Types

#### 1. Code Node

Executes Python code in a sandboxed environment.

```yaml
- id: process_data
  type: code
  code:
    type: fixed
    value: |
      # Access state variables
      input_value = alita_state.get('input_var')

      # Process data
      result = do_something(input_value)

      # CRITICAL: Last expression is the return value
      result
  input:
    - input_var                   # Variables read from state
  output:
    - messages                    # Variables written to state
  structured_output: false        # MUST be false for code nodes
  transition: next_node
```

**CRITICAL RULES for Code Nodes:**

1. **Return Value**: The LAST EXPRESSION in the code block is the return value
   ```python
   # CORRECT - returns test_results dict
   test_results = {"test_passed": True, "data": result}
   test_results

   # WRONG - returns None (assignment is not an expression)
   test_results = {"test_passed": True, "data": result}
   ```

2. **structured_output**: MUST be `false` for code nodes that return a single value

3. **State Access**: Use `alita_state.get('var_name')` to read variables

4. **Available Modules**: `json`, `re`, `time`, `random`, `string`, `math`

#### 2. Toolkit Node

Invokes an external toolkit tool.

```yaml
- id: call_github
  type: toolkit
  tool: list_branches_in_repo     # Tool name from toolkit
  toolkit_name: ${GITHUB_TOOLKIT_NAME}
  input:
    - branch_name                 # State variables needed
  input_mapping:                  # Map state vars to tool params
    branch_name:                  # Tool parameter name
      type: variable
      value: branch_name          # State variable name
  output:
    - tool_result                 # Where to store result
  structured_output: true
  transition: next_node
```

**Rules for Toolkit Nodes:**
1. `tool:` must match exact tool name from toolkit
2. `input_mapping:` maps state variables to tool parameters
3. Left side of mapping = tool parameter name
4. Right side `value:` = state variable name
5. `structured_output: true` for toolkit nodes

#### 3. LLM Node

Invokes an LLM with structured output.

```yaml
- id: generate_data
  type: llm
  input_mapping:
    system:
      type: fixed
      value: "You are a helpful assistant."
    task:
      type: fixed
      value: "Generate a greeting and a number."
    chat_history:
      type: fixed
      value: []
  output:
    - greeting
    - number
  structured_output: true
  structured_output_dict:         # Define expected output schema
    greeting: "str"
    number: "int"
  transition: next_node
```

### Test Result Format

**All test pipelines MUST output a result with `test_passed` field.**

```python
# Standard test result structure
test_results = {
    "test_passed": True,          # REQUIRED: boolean
    "tool_executed": True,        # Whether tool ran
    "actual_value": value,        # What was received
    "expected_value": expected,   # What was expected
    "error": None                 # Error message if any
}
test_results  # Return it!
```

### Transitions

```yaml
transition: next_node_id    # Go to specific node
transition: END             # End pipeline execution
```

### Variable Substitution

Use `${VAR_NAME}` for values replaced at seed time:

```yaml
toolkits:
  - id: ${GITHUB_TOOLKIT_ID}      # Replaced with actual ID
    name: ${GITHUB_TOOLKIT_NAME}  # Replaced with actual name
```

Available substitutions (set via env or CLI):
- `${GITHUB_TOOLKIT_ID}` - GitHub toolkit ID
- `${GITHUB_TOOLKIT_NAME}` - GitHub toolkit name

---

## Complete Example: Toolkit Test

```yaml
name: "GH1 - List Branches"
description: "Verify list_branches tool returns repository branches"

toolkits:
  - id: ${GITHUB_TOOLKIT_ID}
    name: ${GITHUB_TOOLKIT_NAME}

state:
  input:
    type: str
  messages:
    type: list
  tool_result:
    type: str
  test_results:
    type: dict

entry_point: invoke_list_branches

nodes:
  - id: invoke_list_branches
    type: toolkit
    tool: list_branches_in_repo
    toolkit_name: ${GITHUB_TOOLKIT_NAME}
    input: []
    input_mapping: {}
    output:
      - tool_result
    structured_output: true
    transition: process_results

  - id: process_results
    type: code
    code:
      type: fixed
      value: |
        result = alita_state.get('tool_result')

        tool_executed = result is not None
        has_branches = isinstance(result, list) and len(result) > 0

        test_results = {
            "test_passed": tool_executed and has_branches,
            "tool_executed": tool_executed,
            "branches_count": len(result) if isinstance(result, list) else 0,
            "error": None
        }
        test_results
    input:
      - tool_result
    output:
      - messages
    structured_output: false
    transition: END
```

---

## Naming Conventions

| Test Suite | Prefix | Example |
|------------|--------|---------|
| GitHub Toolkit | GH | GH1 - List Branches |
| Structured Output | TC | TC1 - Basic Types |
| State Retrieval | SR | SR1 - Basic Types |
| Custom | XX | XX1 - Custom Test |

---

## Troubleshooting

### "Execution result is missing"

**Cause:** Code node doesn't return a value.

**Fix:** Add variable as last expression:
```python
# Wrong
result = {"test_passed": True}

# Correct
result = {"test_passed": True}
result
```

### Test shows "?" status

**Cause:** No `test_passed` field in output.

**Fix:** Ensure code node returns dict with `test_passed`:
```python
test_results = {
    "test_passed": all_checks_passed,
    # ... other fields
}
test_results
```

### Toolkit parameter not found

**Cause:** Wrong parameter name in `input_mapping`.

**Fix:** Check toolkit's actual parameter names:
```yaml
input_mapping:
  branch_name:          # Must match tool's parameter name
    type: variable
    value: my_var       # Your state variable
```
