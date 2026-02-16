# Test Pipelines Framework

Declarative test automation framework for Alita SDK toolkits and pipelines.

## What is This?

A comprehensive testing framework that validates Alita SDK components through declarative YAML pipeline definitions. Test toolkits, pipeline features, state management, and LLM integrations with automated setup, execution, and reporting.

## Framework Capabilities

- **Toolkit Integration Testing** - Validate toolkit operations with real API calls
- **Pipeline Testing** - Test state management, node types, transitions, and structured outputs
- **Automated Setup/Cleanup** - Programmatic environment creation and teardown
- **Root Cause Analysis** - Automatic RCA on test failures with code search
- **Local & Remote Execution** - Run tests locally or on platform
- **HTML Reports** - Interactive reports with test details and RCA insights
- **Parallel Execution** - Run multiple tests concurrently

## Directory Structure

```
test_pipelines/
├── run_all_suites.sh           # Run all test suites
├── run_all_suites.py           # Python version (for debugging)
├── run_test.sh                 # Run individual tests
├── run_test.py                 # Python version (for debugging)
├── manage_tests.py             # Unified test runner
├── scripts/                    # Implementation scripts
│   ├── setup.py               # Setup environments
│   ├── seed_pipelines.py      # Seed pipelines to platform
│   ├── run_suite.py           # Execute test suites
│   ├── cleanup.py             # Clean up artifacts
│   └── generate_report.py     # Generate HTML reports
├── composable/                 # Shared reusable pipelines (RCA, etc.)
├── configs/                    # Shared toolkit configurations
└── suites/                     # Test suites
    └── <suite_name>/
        ├── pipeline.yaml       # Suite configuration
        ├── tests/              # Test case YAML files
        ├── configs/            # Suite-specific configs (optional)
        └── README.md           # Suite documentation
```

## Suite Configuration

Each suite contains a `pipeline.yaml` that defines:
- **setup** - Steps to create toolkits and test environment
- **composable_pipelines** - Reusable pipelines (RCA, validation, etc.)
- **execution** - Test directory, order, and settings
- **hooks** - Automated actions (post_test RCA on failures, etc.)
- **cleanup** - Steps to remove test artifacts

See individual suite README files for specific configurations.

## Running Tests

### Quick Start

```bash
# Run all test suites
./run_all_suites.sh

# Run specific suites
./run_all_suites.sh <suite1> <suite2>

# Run individual test
./run_test.sh suites/<suite_name> <test_pattern>

# Local mode (no backend)
./run_test.sh --local suites/<suite_name> <test_pattern>
```

### Available Scripts

| Script | Purpose | Key Options |
|--------|---------|-------------|
| `run_all_suites.sh` | Run all suites with full workflow | `-v`, `--local`, `--skip-cleanup`, `--stop-on-failure` |
| `run_test.sh` | Run individual tests | `--setup`, `--seed`, `--local`, `--cleanup`, `--all` |
| `scripts/setup.py` | Create toolkits and environment | `--verbose`, `--output-env .env` |
| `scripts/seed_pipelines.py` | Seed pipelines to platform | `--verbose`, `--dry-run` |
| `scripts/run_suite.py` | Execute test suite | `--verbose`, `--json`, `--local`, `--fail-fast` |
| `scripts/cleanup.py` | Remove test artifacts | `--yes`, `--verbose`, `--dry-run` |
| `scripts/generate_report.py` | Generate HTML report | Takes results.json path |

### Python Versions (For Debugging)

```bash
# Python versions for IDE debugging
python run_all_suites.py <suite1> <suite2>
python run_test.py suites/<suite_name> <test_pattern>
python manage_tests.py run --suite <suite_name> --pattern <test_pattern>
```

### Common Options

- `--verbose` / `-v` - Detailed output
- `--local` - Run locally without backend
- `--json` - JSON output format
- `--setup` - Run setup before test
- `--seed` - Seed pipeline before running
- `--cleanup` - Clean up after running
- `--all` - Full workflow (setup + seed + run + cleanup)
- `--stop-on-failure` - Stop on first failure
- `--skip-cleanup` - Keep resources after execution

## Debugging Tests

### Local Execution

Run tests locally without backend:
```bash
./run_test.sh --local suites/<suite_name> <test_pattern>
python run_test.py --local suites/<suite_name> <test_pattern>
```

### Iterative Development

```bash
# First run: full setup
./run_test.sh --setup --seed suites/<suite_name> <test_pattern>

# Quick iterations (no setup/seed)
./run_test.sh suites/<suite_name> <test_pattern>

# After YAML changes
./run_test.sh --seed suites/<suite_name> <test_pattern>
```

### Python Debugging

Use Python scripts with IDE breakpoints:
```bash
python run_test.py --local suites/<suite_name> <test_pattern>
python manage_tests.py run --suite <suite_name> --pattern <test_pattern> --local
```

### Viewing Results

```bash
# JSON output
python scripts/run_suite.py suites/<suite_name> --json > results.json

# Generate HTML report
python scripts/generate_report.py results.json
# Opens results.html in same directory
```

### Test Output

Results are saved to `test_results/suites/<suite_name>/`:
- `results.json` - Test results with RCA
- `results.html` - Interactive HTML report
- `*.log` - Execution logs (setup, seed, run, cleanup)

## Environment Setup

**IMPORTANT:** The framework uses `.env` file to resolve variables in `pipeline.yaml` and test files. Variables like `${GITHUB_TOOLKIT_ID}`, `${API_KEY}`, etc. are substituted from `.env` during setup, seeding, and execution.

Create `.env` file in test_pipelines directory:
```bash
# Platform connection (required)
DEPLOYMENT_URL=https://dev.elitea.ai
API_KEY=your_api_key
PROJECT_ID=your_project_id

# Suite-specific variables
# See suite's README.md or pipeline.yaml for required variables
# Example for github suite:
# GIT_TOOL_ACCESS_TOKEN=ghp_xxxxxxxxxxxx
# GITHUB_TEST_REPO=ProjectAlita/elitea-testing
# GITHUB_BASE_BRANCH=main
# GITHUB_SECRET_NAME=github
# GITHUB_TOOLKIT_NAME=testing

# Optional: RCA configuration
RCA_MODEL=gpt-4o-mini
SDK_TOOLKIT_ID=your_sdk_toolkit_id
```

**Variable Resolution:**
- `${VAR_NAME}` - Required variable, fails if not found
- `${VAR_NAME:default}` - Optional variable with default value
- Variables are resolved during setup, seeding, and test execution
- Variables set by setup steps (via `save_to_env`) are available for later steps

## Discovering Suites

```bash
# List available suites
ls -d suites/*/

# View suite documentation
cat suites/<suite_name>/README.md

# View suite configuration
cat suites/<suite_name>/pipeline.yaml
```

## Test Case YAML Format

### Basic Structure

Each test case is a YAML file with this structure:

```yaml
name: "Test Name"
description: |
  Test description explaining the objective and expected behavior

toolkits:
  - id: ${TOOLKIT_ID}        # From .env
    name: ${TOOLKIT_NAME}    # From .env

state:                       # Define pipeline state variables
  variable_name:
    type: str|int|dict|list
    value: "initial value"
  result:
    type: str                # Output variable (no initial value)

entry_point: first_node     # Starting node ID

nodes:
  - id: node_id
    type: toolkit|llm|code
    # ... node configuration ...
    transition: next_node|END
```

### Node Types

#### Toolkit Node

Executes a toolkit tool and captures the result:

```yaml
- id: invoke_tool
  type: toolkit
  input: [file_path, content]        # List of input variables
  input_mapping:                     # Map variables to tool parameters
    file_path:
      type: variable
      value: file_path
    content:
      type: fixed
      value: "Fixed value"
  output: [tool_result]              # Variables to store output
  structured_output: true            # Parse output as structured data
  continue_on_error: true            # Continue pipeline if tool fails (for negative tests)
  tool: tool_name                    # Tool name from toolkit
  toolkit_name: ${TOOLKIT_NAME}      # Toolkit to use
  transition: next_node
```

**Key Properties:**
- `continue_on_error: true` - **Critical for negative tests**. When set, allows the pipeline to continue to the next node even if the tool encounters an error. This enables validation nodes to check that errors are handled properly.
- `structured_output: true` - Parses tool output and updates state variables that match output keys
- `input_mapping` - Maps state variables or fixed values to tool parameters

#### LLM Node

Uses an LLM to validate results or perform analysis:

```yaml
- id: validate_results
  type: llm
  input: [tool_result, expected_values]
  input_mapping:
    chat_history:
      type: fixed
      value: []
    system:
      type: fixed
      value: "You are a validator. Return only valid JSON."
    task:
      type: fstring
      value: |
        Analyze the tool output: {tool_result}
        Expected: {expected_values}
        
        Return JSON:
        {{
          "test_passed": boolean,
          "validation_details": "description"
        }}
  model: ${DEFAULT_LLM_MODEL}
  output: [validation_result]
  structured_output_dict:
    validation_result: dict
  transition: END
```

**Key Properties:**
- `structured_output_dict` - Defines output variable types for parsing LLM response
- `task` with `type: fstring` - Template string with variable substitution using `{var_name}` syntax

### Error Handling with continue_on_error

The `continue_on_error: true` flag is essential for **negative testing** - tests that verify error handling behavior.

**How it works:**

1. **Without continue_on_error (default behavior):**
   ```yaml
   - id: invoke_tool
     type: toolkit
     tool: update_file
     # ... config ...
     transition: validate_results  # Never reached if tool fails
   ```
   - If the tool encounters an error, the pipeline stops immediately
   - The test is marked as failed
   - Validation nodes never execute

2. **With continue_on_error: true:**
   ```yaml
   - id: invoke_tool
     type: toolkit
     tool: update_file
     continue_on_error: true  # ← Key difference
     transition: validate_results  # ← Always reached, even on error
   
   - id: validate_results
     type: llm
     # Validates that the error was handled correctly
   ```
   - If the tool encounters an error, it's captured in the output
   - The pipeline continues to the next node (validate_results)
   - Validation can check that the error message is appropriate
   - Test passes if error handling is correct

**Example Use Case:**

Test that `update_file` properly handles non-existent files:

```yaml
- id: invoke_update_file
  type: toolkit
  tool: update_file
  input_mapping:
    file_path:
      type: variable
      value: non_existent_file  # This will cause an error
  continue_on_error: true  # ← Let's us validate the error
  transition: validate_error_handling

- id: validate_error_handling
  type: llm
  input_mapping:
    task:
      type: fstring
      value: |
        Tool result: {tool_result}
        
        Verify:
        1. Error message contains "File not found" or similar
        2. No unhandled exceptions (traceback, stack trace)
        3. Error is properly formatted
        
        Return {{"test_passed": true}} if error handled correctly.
```

**Best Practices:**
- Use `continue_on_error: true` only for nodes that are expected to fail
- Always follow with a validation node that checks the error output
- Document in test description that this is a negative test
- Include expected error indicators in state variables for validation

## Logging & Output Flow (--local mode)

### Output Routing Summary

| **Output Source** | **Destination** | **Content** | **Format** | **Control Flag** |
|-------------------|-----------------|-------------|------------|------------------|
| **Python logging.getLogger()** | `run.log` (FileHandler) | All levels: DEBUG, INFO, WARNING, ERROR from all modules | `%(asctime)s - %(name)s - %(levelname)s - %(message)s` | Always enabled |
| **Python logging.getLogger()** | Console (StreamHandler) | `-v`: INFO (utils_local only) + WARNING/ERROR (all)<br>`no -v`: WARNING/ERROR (all) | Plain text with ANSI codes | `-v` flag |
| **TestLogger (custom)** | stderr → `run.log` (via tee) + Console | Test progress messages with ANSI color codes | `[INFO] message`, `[ERROR] message` | Always enabled |
| **print()** statements | stdout → Console | Debug/info messages from scripts | Plain text | Always enabled |
| **--output-json** | `results.json` | Test results structure (pass/fail, assertions, timing) | JSON | `--output-json` flag |

### Shell Redirection Pattern

```bash
# run_all_suites.sh
python scripts/run_suite.py "$suite_spec" $VERBOSE --output-json "$results_file" \
  2> >(tee "$suite_output_dir/run.log" >&2)
```

**How it works:**
- `2>` redirects stderr to process substitution
- `tee` reads stdin, writes to both `run.log` file AND stdout
- `>&2` redirects tee's stdout back to stderr
- **Result**: stderr → tee → (run.log + stderr passthrough to console)

### What Appears Where

| **File/Stream** | **Content** | **Filtering** |
|-----------------|-------------|---------------|
| **run.log** | • Python logging (DEBUG+) with timestamps/logger names<br>• TestLogger stderr (ANSI codes)<br>• All error messages | None - captures everything |
| **Console** | • `-v`: INFO from utils_local + WARNING/ERROR from all<br>• `no -v`: Only WARNING/ERROR from all<br>• TestLogger progress messages<br>• print() statements | ConsoleInfoFilter + verbose flag |
| **results.json** | • Test execution results<br>• Assertions pass/fail<br>• Timing data<br>• Error messages | Only test results (no logs) |

### Key Implementation Details

1. **FileHandler** (run.log): Writes directly to file, DEBUG level, includes all alita_sdk modules
2. **StreamHandler** (console): Writes to stderr, INFO/WARNING level depending on `-v`, filtered by ConsoleInfoFilter
3. **ConsoleInfoFilter**: Custom filter allowing only utils_local INFO on console, blocks all DEBUG
4. **configure_file_logging()**: Called once in run_suite.py to set up DEBUG file logging
5. **Logger configuration order**: Third-party loggers configured first, then alita_sdk loggers overridden to DEBUG

### How It All Works Together

#### run_all_suites.sh (with tee redirection)

Complete output flow from Python scripts to final destinations:

```
┌─────────────────────────────────────────┐
│     Python scripts (run_suite.py)       │
└──────────────────┬──────────────────────┘
                   │
        ┌──────────┼──────────┐
        ↓          ↓          ↓
    stdout      stderr    FileHandler
    (print)   (logging,   (direct to
     |        TestLogger)   run.log)
     |          |              |
     |          └──────┬───────┘
     |                 ↓
     |          [shell: 2> >()]
     |          (tee reads stderr)
     |                 │
     |        ┌────────┴────────┐
     |        ↓                 ↓
     |      run.log          stderr
     |      (file)         (console)
     │                        │
     └────────────┬───────────┘
                  ↓
             Console Display
   (prints, logs, errors all mixed)
```

**Key Points:**
- **stdout** (print statements) → Console directly
- **stderr** (logging, TestLogger) → Shell redirects through `tee` → run.log + Console
- **FileHandler** → run.log directly (bypasses stdout/stderr, formatted output)
- **Console** receives: stdout + stderr (mixed together)
- **run.log** receives: FileHandler output + tee-captured stderr

#### run_test.sh (no tee redirection)

Simpler flow without stderr capture:

```
┌─────────────────────────────────────────┐
│     Python scripts (run_suite.py)       │
└──────────────────┬──────────────────────┘
                   │
        ┌──────────┼──────────┐
        ↓          ↓          ↓
    stdout      stderr    FileHandler
    (print)   (logging,   (direct to
     |        TestLogger)   run.log)
     |          |              |
     |          ↓              ↓
     │        Console       run.log
     │                        │
     └────────────┬───────────┘
                  ↓
             Terminal Display
```

**Key Differences:**
- **run_all_suites.sh**: Uses `2> >(tee run.log >&2)` to capture stderr to both file and console
- **run_test.sh**: No tee, stderr goes directly to console (TestLogger output not saved to run.log)
- **Both**: FileHandler always writes formatted DEBUG logs directly to run.log

**Why This Design:**
```
Test Output Routing:
├─ stdout (print) → Console only
├─ stderr (logging/TestLogger) → Console + run.log (via tee)
└─ FileHandler → run.log only (formatted, DEBUG level)

Results:
✓ Console shows: real-time progress (filtered)
✓ run.log shows: everything (DEBUG + raw ANSI)
✓ results.json shows: test results only
```

## Creating New Suites

1. Create suite directory structure:
```bash
cd test_pipelines/suites
mkdir my_suite && cd my_suite
mkdir tests configs
```

2. Create `pipeline.yaml` with setup, execution, and cleanup configuration

3. Create test case YAML files in `tests/` directory

4. Test the suite:
```bash
./run_test.sh --all suites/my_suite test_case_01
```
