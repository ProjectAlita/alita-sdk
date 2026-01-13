# Pipeline Test Framework

Execute and validate toolkit test pipelines on the Elitea platform.

## Quick Start

```bash
# Set environment variables (or use .env file)
export AUTH_TOKEN="your_api_key"
export BASE_URL="http://192.168.68.115"
export PROJECT_ID="2"
export GITHUB_TOOLKIT_ID="71"

# Seed pipelines
python seed_pipelines.py github_toolkit

# Run all tests
python run_suite.py --pattern "GH*"

# Run single test
python run_pipeline.py --name "GH1 - List Branches"
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

## Complete Example: LLM Structured Output Test

```yaml
name: "TC1 - Basic Types"
description: "Verify LLM structured output with basic types"

state:
  input:
    type: str
  messages:
    type: list
  greeting:
    type: str
  count:
    type: int
  test_results:
    type: dict

entry_point: generate_output

nodes:
  - id: generate_output
    type: llm
    input_mapping:
      system:
        type: fixed
        value: "You are a helpful assistant."
      task:
        type: fixed
        value: "Generate a greeting and the number 42."
      chat_history:
        type: fixed
        value: []
    output:
      - greeting
      - count
    structured_output: true
    structured_output_dict:
      greeting: "str"
      count: "int"
    transition: verify_output

  - id: verify_output
    type: code
    code:
      type: fixed
      value: |
        greeting = alita_state.get('greeting')
        count = alita_state.get('count')

        greeting_ok = isinstance(greeting, str) and len(greeting) > 0
        count_ok = count == 42

        test_results = {
            "test_passed": greeting_ok and count_ok,
            "greeting_is_string": greeting_ok,
            "count_is_42": count_ok,
            "actual_greeting": greeting,
            "actual_count": count
        }
        test_results
    input:
      - greeting
      - count
    output:
      - messages
    structured_output: false
    transition: END
```

---

## Common Patterns

### Pattern 1: Setup → Execute → Verify

```yaml
nodes:
  - id: setup
    type: code
    # Prepare test data
    transition: execute

  - id: execute
    type: toolkit
    # Call the tool being tested
    transition: verify

  - id: verify
    type: code
    # Check results, set test_passed
    transition: END
```

### Pattern 2: Generate Unique Names

```python
import time
import random
import string

timestamp = time.strftime('%Y-%m-%d')
suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
unique_name = f"test-{timestamp}-{suffix}"
unique_name
```

### Pattern 3: Multi-Step Toolkit Test

```yaml
nodes:
  - id: step1_set_branch
    type: toolkit
    tool: set_active_branch
    transition: step2_create_file

  - id: step2_create_file
    type: toolkit
    tool: create_file
    transition: verify

  - id: verify
    type: code
    # Verify all steps succeeded
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

## Scripts Reference

### seed_pipelines.py

Deploy YAML files to platform:

```bash
python seed_pipelines.py <folder> [options]

Options:
  --base-url URL          Platform URL
  --project-id ID         Target project
  --github-toolkit-id ID  Toolkit ID for substitution
  --dry-run               Preview without creating
  -v, --verbose           Detailed output
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

### run_pipeline.py

Execute single pipeline:

```bash
python run_pipeline.py <id> [options]
python run_pipeline.py --name "Pipeline Name" [options]

Options:
  --json                  JSON output
  --exit-code             Exit 0=pass, 1=fail
  -v, --verbose           Detailed output
  --timeout SECONDS       Execution timeout
```

### run_suite.py

Execute multiple pipelines:

```bash
python run_suite.py [options]

Options:
  --pattern PATTERN       Name pattern (repeatable)
  --ids ID [ID ...]       Specific IDs
  <folder>                Run from folder
  --parallel N            Parallel execution
  --json                  JSON output
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

# Toolkit substitution
GITHUB_TOOLKIT_ID=71
GITHUB_TOOLKIT_NAME=testing
```

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
