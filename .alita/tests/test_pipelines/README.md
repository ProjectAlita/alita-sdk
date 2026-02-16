# Alita SDK Test Pipelines Framework

**Declarative end-to-end testing framework for Alita SDK toolkits and agents**

## Overview

A comprehensive, production-grade testing system that validates Alita SDK components through declarative YAML pipeline definitions. Designed for CI/CD integration with automated setup, execution, RCA on failures, and detailed reporting.

### Key Capabilities

| Feature | Description |
|---------|-------------|
| **Toolkit Integration Testing** | Validate 60+ toolkit operations with real API calls (JIRA, GitHub, GitLab, etc.) |
| **Pipeline State Testing** | Test state management, node transitions, structured outputs, error handling |
| **Negative Testing** | Validate error handling with `continue_on_error` for expected failures |
| **Automated Setup/Cleanup** | Programmatic environment creation (toolkits, configs) and teardown |
| **Root Cause Analysis** | Automatic RCA on failures with code search and impact analysis |
| **Dual Execution Modes** | Run locally (SDK-only) or remotely (Alita Platform) |
| **Interactive Reports** | HTML reports with test details, RCA insights, and timing data |
| **CI/CD Integration** | GitHub Actions workflows with Docker, parallel execution, auto-analysis |

### Architecture

**Execution Flow**: Setup → Seed → Run → Cleanup → Report
1. `setup.py` - Create toolkits, configs (save IDs to .env)
2. `seed_pipelines.py` - Upload pipelines to platform
3. `run_suite.py` - Execute tests (local or platform)
4. `cleanup.py` - Delete artifacts
5. `generate_report.py` - Generate HTML report

**Tech Stack**: LangGraph (pipelines), AlitaClient (LLMs), YAML configs, Python logging, HTML reports

---

## Quick Start

### Prerequisites

```bash
# Required environment variables in .env
DEPLOYMENT_URL=https://dev.elitea.ai
API_KEY=your_api_key
PROJECT_ID=your_project_id

# Toolkit-specific credentials (see suite README for requirements)
GITHUB_TOKEN=ghp_xxxxx
JIRA_API_KEY=xxxxx
# ... etc
```

### Run Your First Test

```bash
cd .alita/tests/test_pipelines
./run_test.sh --all suites/ado ADO01  # Full workflow
./run_test.sh --local suites/ado ADO01  # Local mode (fast)
./run_all_suites.sh ado  # Entire suite
```

Results in `test_results/suites/<suite>/`: `results.json`, `results.html`, `*.log`

---

## Directory Structure

```
test_pipelines/
├── run_all_suites.sh           # Execute all test suites
├── run_test.sh                 # Run individual tests (development)
├── manage_tests.py             # Unified Python test runner
│
├── scripts/                    # Core implementation
│   ├── setup.py               # Create toolkits & configurations
│   ├── seed_pipelines.py      # Upload pipelines to platform
│   ├── run_suite.py           # Execute test suite
│   ├── cleanup.py             # Delete test artifacts
│   ├── generate_report.py     # Generate HTML reports
│   ├── utils_common.py        # Shared utilities (config loading)
│   ├── utils_local.py         # Local execution engine
│   └── logger.py              # Unified logging system
│
├── composable/                 # Shared reusable pipelines
│   ├── rca_on_failure.yaml    # Auto RCA on test failures
│   └── rca_negative_test.yaml # RCA for negative tests
│
├── configs/                    # Shared toolkit configurations
│   ├── github-config.json     # GitHub toolkit template
│   ├── jira-config.json       # JIRA toolkit template
│   └── ...                    # 40+ toolkit configs
│
├── suites/                     # Test suites (organized by toolkit)
│   └── <suite_name>/
│       ├── pipeline.yaml      # Suite configuration (setup/cleanup)
│       ├── README.md          # Suite documentation
│       ├── tests/             # Test case YAML files
│       │   ├── test_case_01_*.yaml
│       │   └── test_case_02_*.yaml
│       └── configs/           # Suite-specific configs (optional)
│
└── test_results/               # Execution results
    └── suites/<suite_name>/
        ├── results.json       # Test results (JSON)
        ├── results.html       # Interactive report (HTML)
        └── *.log              # Execution logs
```

---

## Execution Modes

### 1. Full Suite Execution (`run_all_suites.sh`)

```bash
./run_all_suites.sh ado github  # Run specific suites
./run_all_suites.sh -v ado  # Verbose
./run_all_suites.sh --local --skip-cleanup ado  # Local, keep artifacts
```

**Key Options**: `-v` (verbose), `--local` (no backend), `--skip-cleanup`, `--stop-on-failure`

### 2. Individual Test Execution (`run_test.sh`)

```bash
./run_test.sh --all suites/ado ADO01  # Full workflow
./run_test.sh --setup --seed suites/ado ADO01  # First time
./run_test.sh suites/ado ADO01  # Quick run (after setup)
./run_test.sh --seed suites/ado ADO01  # After YAML changes
./run_test.sh -v --local --timeout 300 suites/ado ADO01  # Debug
```

**Key Options**: `--setup`, `--seed`, `--cleanup`, `--all`, `--local`, `-v`, `--timeout SEC`

**Dev Workflow**: (1) `--setup --seed` once → (2) iterate without flags → (3) `--seed` after YAML edits

### 3. Local Mode (No Backend)

Runs tests entirely in SDK without platform. Use `--local` flag for fast feedback.

**Benefits**: No network, faster (3-10x), IDE debugging, offline development
**Tech**: Direct toolkit imports, in-memory LangGraph, AlitaClient for LLMs
**Limits**: No platform storage, requires SDK + toolkit dependencies

### 4. Docker Execution (CI/CD)

```bash
docker compose up  # Default: run_all_suites.sh
export DOCKER_COMMAND=".alita/tests/test_pipelines/run_test.sh --local suites/ado ADO01"
docker compose up  # Custom command
```

**Key Features**: Git safe.directory fix, dynamic commands via `$DOCKER_COMMAND`, volume mounts for live updates

---

## Test Case YAML Format

### Basic Structure

Tests are declarative YAML files defining a state machine:

```yaml
name: "Test Name"
description: |
  Multi-line description of test objective,
  expected behavior, and validation criteria

toolkits:
  - id: ${TOOLKIT_ID}        # From .env (set by setup.py)
    name: ${TOOLKIT_NAME}    # From .env

state:                       # Pipeline state variables
  input_var:
    type: str|int|dict|list  # Variable type
    value: "initial value"   # Initial value
  output_var:
    type: str                # Output variables have no initial value

entry_point: first_node_id   # Starting node

nodes:
  - id: node_id
    type: toolkit|llm|code   # Node type
    # ... node configuration ...
    transition: next_node|END  # Next node or END
```

### Node Types

#### 1. Toolkit Node

Executes a toolkit tool and captures output.

```yaml
- id: invoke_tool
  type: toolkit
  tool: tool_name                    # Tool from toolkit (e.g., update_file)
  toolkit_name: ${TOOLKIT_NAME}      # Toolkit to use
  
  input: [var1, var2]                # Input variables from state
  input_mapping:                     # Map state → tool parameters
    parameter_name:
      type: variable|fixed|fstring   # Mapping type
      value: var1                    # Variable name, fixed value, or template
  
  output: [result_var]               # Variables to store output
  structured_output: true|false      # Parse output as JSON/structured data
  continue_on_error: true|false      # Continue on failure (for negative tests)
  
  transition: next_node              # Next node ID or END
```

**Mapping Types**: `variable` (state var), `fixed` (literal), `fstring` (template with `{var}`)

**Output**: `structured_output: false` (string) or `true` (parse JSON, update state)

**Errors**: `continue_on_error: true` captures errors for validation (negative tests)

#### 2. LLM Node

Uses LLM for validation, analysis, or decision-making.

```yaml
- id: validate_results
  type: llm
  model: ${DEFAULT_LLM_MODEL}        # LLM model (from .env)
  
  input: [var1, var2]                # Input variables
  input_mapping:
    chat_history:
      type: fixed
      value: []                      # Empty chat history
    system:
      type: fixed
      value: "You are a validator. Return only valid JSON."
    task:
      type: fstring
      value: |
        Analyze the tool output: {var1}
        Expected: {var2}
        
        Return JSON: {{ "test_passed": boolean, "reason": "string" }}
  
  output: [validation_result]        # Store LLM response
  structured_output_dict:            # Parse LLM output as structured data
    validation_result: dict          # Type annotation for output
  
  transition: END
```

**Structured Output**:
- `structured_output_dict` → Defines output variable types for parsing
- LLM response is parsed as JSON and validates against schema
- Example:
  ```yaml
  structured_output_dict:
    test_results: dict
    metrics: dict
  # state.test_results = {"test_passed": true, ...}
  # state.metrics = {"tokens": 150, ...}
  ```

**Prompt Tips**: Use `{var}` for substitution, `{{ }}` for literal JSON braces

#### 3. Code Node
*(Future: custom Python execution)*

---

## Suite Configuration (`pipeline.yaml`)

Each suite has a `pipeline.yaml` defining the test environment lifecycle:

```yaml
name: suite_name
description: Suite description

# Environment variable mapping (from .env)
env_mapping:
  toolkit_config: ${CONFIG_PATH:../../configs/default.json}
  api_token: ${API_TOKEN}

# Setup: Create environment before tests
setup:
  - name: Setup Configuration
    type: configuration
    config:
      config_type: github            # Configuration type
      alita_title: github-creds      # Secret name on platform
      data:
        token: ${GITHUB_TOKEN}
    
  - name: Create Toolkit
    type: toolkit
    action: create_or_update
    config:
      config_file: ../../configs/github-config.json
      toolkit_type: github
      toolkit_name: ${TOOLKIT_NAME:github-testing}
    save_to_env:                     # Save results to .env
      - key: GITHUB_TOOLKIT_ID
        value: $.id                  # JSONPath to extract value
      - key: GITHUB_TOOLKIT_NAME
        value: $.name

# Composable pipelines (RCA, validation, etc.)
composable_pipelines:
  - ../../composable/rca_on_failure.yaml

# Execution configuration
execution:
  test_directory: tests
  order:
    - test_case_*.yaml               # File patterns
  
  substitutions:                     # Variables for test files
    TOOLKIT_ID: ${GITHUB_TOOLKIT_ID}
    TOOLKIT_NAME: ${GITHUB_TOOLKIT_NAME}
    DEFAULT_LLM_MODEL: ${DEFAULT_LLM_MODEL:gpt-4o}
  
  settings:
    timeout: 180                     # Per-test timeout (seconds)
    parallel: 1                      # Parallel execution (not implemented)
    stop_on_failure: false           # Stop on first failure

# Cleanup: Delete artifacts after tests
cleanup:
  - name: Delete Test Pipelines
    type: pipeline
    config:
      pattern: "GH*"                 # Delete pipelines matching pattern
    continue_on_error: true
  
  - name: Delete Toolkit
    type: toolkit
    config:
      toolkit_id: ${GITHUB_TOOLKIT_ID}
    enabled: true
    continue_on_error: true
```

**Setup Types**: `configuration` (creds), `toolkit` (create), `toolkit_invoke` (invoke tool)
**Cleanup**: Use `continue_on_error: true` to ignore already-deleted resources

---

## Negative Testing

**Negative tests** validate error handling by intentionally triggering failures. The `continue_on_error` flag is critical for these tests:

### Problem: Pipeline Stops on Tool Errors

**Default behavior** (without `continue_on_error`):
```yaml
- id: invoke_tool
  type: toolkit
  tool: update_file
  # ... config ...
  transition: validate_results  # ❌ Never reached if tool fails
```
- Tool encounters error → Pipeline stops immediately
- Test marked as failed
- Validation node never executes → Can't verify error handling

### Solution: `continue_on_error: true`

```yaml
- id: invoke_tool_expecting_failure
  type: toolkit
  tool: update_file
  input_mapping:
    file_path:
      type: variable
      value: nonexistent_file  # ⚠️ Intentional error
  continue_on_error: true      # ✅ Capture error, continue
  output: [tool_result]
  transition: validate_error_handling  # ✅ Always reached

- id: validate_error_handling
  type: llm
  input: [tool_result]
  input_mapping:
    task:
      type: fstring
      value: |
        Tool result: {tool_result}
        
        Verify proper error handling:
        1. Error message contains "File not found" or similar
        2. No unhandled exceptions (no stack traces)
        3. Error is properly formatted
        
        Return {{"test_passed": true}} if error handled correctly,
        {{"test_passed": false}} otherwise.
  # ... rest of validation ...
```

### How It Works

1. Tool encounters error → Captured in output
2. Pipeline continues to validation node
3. Validation checks error message quality
4. Test passes if error handled correctly

✅ **DO**: Use for expected failures, always validate, document intent
❌ **DON'T**: Use for success cases, skip validation, ignore empty errors

### Example: Negative Test

```yaml
name: "ADO21 - Update File: Non-existent File (Negative)"
state:
  file_path: { type: str, value: "nonexistent.txt" }
  tool_result: { type: str }

nodes:
  - id: invoke_tool
    type: toolkit
    tool: update_file
    input_mapping:
      file_path: { type: variable, value: file_path }
    output: [tool_result]
    continue_on_error: true
    transition: validate_error
  
  - id: validate_error
    type: llm
    input_mapping:
      task:
        type: fstring
        value: |
          Check: {tool_result}
          Validate: (1) not empty (2) contains "not found" (3) no stack trace
          Return: {{"test_passed": bool, "has_error_message": bool}}
    structured_output_dict: { test_results: dict }
    transition: END
```

---

## Logging & Output System

The framework uses a sophisticated dual-logging system optimized for both interactive and file-based output.

### Output Destinations

| **Source** | **Destination** | **Content** | **Control** |
|------------|-----------------|-------------|-------------|
| **Python `logging`** | `run.log` (FileHandler) | All levels (DEBUG, INFO, WARNING, ERROR) | Always enabled |
| **Python `logging`** | Console (StreamHandler) | `-v`: INFO (utils_local) + WARNING/ERROR (all)<br>No `-v`: WARNING/ERROR only | `-v` flag |
| **TestLogger** | stderr → `run.log` (via `tee`) | Test progress with ANSI colors | Always enabled |
| **`print()`** | stdout → Console | Debug messages from scripts | Always enabled |
| **--output-json** | `results.json` | Test results (pass/fail, assertions) | `--output-json` flag |

### Logging Architecture

```
┌──────────────────────────────────────────────────────┐
│ Python Logging (logging.getLogger())                  │
│ • DEBUG: utils_local, run_suite, setup, seed, cleanup│
│ • INFO: Progress, operations, decisions               │
│ • WARNING/ERROR: Issues, failures                     │
└─────────┬──────────────────────┬─────────────────────┘
          │                      │
    ┌─────┴─────┐          ┌────┴────┐
    │FileHandler│          │ Stream  │
    │           │          │ Handler │
    └─────┬─────┘          └────┬────┘
          ↓                     ↓
      run.log              Console
      (DEBUG+)          (-v: INFO+, else: WARN+)

┌──────────────────────────────────────────────────────┐
│ TestLogger (custom colored logger)                    │
│ • [INFO] Test progress                                │
│ • [SUCCESS] ✓ Pass                                    │
│ • [ERROR] ✗ Fail                                      │
└─────────┬────────────────────────────────────────────┘
          │
     stderr →───────┬──────────→ Console (ANSI colors)
                    │
           ┌────────┴──────┐
           │ Shell: tee    │  (in run_all_suites.sh)
           └────────┬──────┘
                    ↓
                run.log (raw ANSI)
```

### Shell Redirection (run_all_suites.sh)

```bash
# Redirect stderr through tee to capture TestLogger output
python scripts/run_suite.py "$suite_spec" $VERBOSE \
  2> >(tee "$suite_output_dir/run.log" >&2)
```

**How it works**:
1. `2>` redirects stderr
2. `>(tee file)` process substitution: reads stdin, writes to both file and stdout
3. `>&2` redirects tee's stdout back to stderr
4. **Result**: stderr → tee → (`run.log` + stderr passthrough to console)

### Log Files

**`run.log`** - Complete execution log:
```
2026-02-16 10:15:23 - utils_local - DEBUG - Loading test: test_case_01.yaml
2026-02-16 10:15:23 - run_suite - INFO - Executing pipeline: ADO01
[INFO] ══ Test: ADO01 - List Files
[INFO] ✓ Node: invoke_list_files (2.3s)
[INFO] ✓ Node: validate_results (1.1s)
[SUCCESS] ✓ Test passed (3.4s total)
```

**`setup.log`** - Setup execution:
```
2026-02-16 10:10:00 - setup - INFO - Creating toolkit: ado-repos-testing
2026-02-16 10:10:01 - setup - INFO - Toolkit created: ID=12345
2026-02-16 10:10:01 - setup - INFO - Saved to .env: ADO_REPOS_TOOLKIT_ID=12345
```

### Verbose Mode

```bash
# Verbose: Real-time progress, all INFO logs
./run_all_suites.sh -v ado

# Normal: Only warnings/errors
./run_all_suites.sh ado
```

**Verbose Mode** (`-v` flag):
- Console shows: INFO logs from `utils_local` + WARNING/ERROR from all
- Useful for: Debugging, understanding execution flow
- Output: More noisy, but complete visibility

**Normal Mode** (no `-v`):
- Console shows: Only WARNING/ERROR logs
- Useful for: CI/CD, production runs, clean output
- Output: Quiet, only important messages

### Logging Configuration (Technical)

**File Logging** (`configure_file_logging()` in logger.py):
```python
# Add FileHandler for DEBUG logs
file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
file_handler.setFormatter(formatter)

# Apply to all loggers
for name in ['alita_sdk', 'utils_local', 'run_suite', 'setup', 'seed_pipelines', 'cleanup']:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)
```

**Console Logging** (StreamHandler with filter):
```python
# Only INFO from utils_local on console (when -v)
class ConsoleInfoFilter(logging.Filter):
    def filter(self, record):
        if record.levelno == logging.INFO:
            return record.name == 'utils_local'  # Only utils_local INFO
        return record.levelno >= logging.WARNING  # All WARNING+
```

---

## Environment Setup

### Required Environment Variables

Create `.env` in `test_pipelines/` directory:

```bash
# Platform Connection (required for all)
DEPLOYMENT_URL=https://dev.elitea.ai
API_KEY=your_api_key
PROJECT_ID=your_project_id

# LLM Configuration
DEFAULT_LLM_MODEL=gpt-4o-2024-11-20

# Toolkit Credentials (suite-specific, see suite README)
# GitHub
GITHUB_TOKEN=ghp_xxxxx
GITHUB_TEST_REPO=owner/repo
GITHUB_BASE_BRANCH=main

# JIRA
JIRA_API_KEY=xxxxx
JIRA_USERNAME=user@example.com
JIRA_BASE_URL=https://yourorg.atlassian.net

# Azure DevOps
ADO_TOKEN=xxxxx
ADO_ORGANIZATION_URL=https://dev.azure.com/yourorg
ADO_PROJECT=YourProject
ADO_REPOSITORY_ID=repo-guid

# ... etc (40+ toolkit configs available)
```

### Environment Variables

**Resolution**: (1) Setup saves IDs to .env → (2) Substitute `${VAR}` or `${VAR:default}` in YAML

**Override**: `export ALITA_ENV_FILE=/path/to/.env`

**Patterns**: `*_TOKEN` (API), `*_API_KEY` (services), `*_BASE_URL`, `*_TOOLKIT_ID` (from setup)

---

## Debugging Tests

### Debugging

**IDE Debugging**: `python scripts/run_suite.py suites/ado --local -v` (set breakpoints in utils_local.py)

**Quick Dev Loop**: (1) `--setup --seed` once → (2) iterate → (3) `--seed` after YAML edits

**Logs**: `cat test_results/suites/ado/run.log | grep -i error`

**JSON Analysis**: `python scripts/run_suite.py suites/ado --json | jq '.tests[] | select(.status=="failed")'`

**Dry Run**: `python scripts/setup.py suites/ado --dry-run`

---

## Creating New Tests

### Creating Tests

**Naming**: `test_case_NN_description.yaml` (zero-padded number)

**Minimal Template**:

```yaml
- id: validate_results
  type: llm
  input: [tool_result, expected_output]
  input_mapping:
    chat_history: { type: fixed, value: [] }
    system: { type: fixed, value: "You are a QA validator. Return only valid JSON." }
    task:
      type: fstring
      value: |
        Tool Result: {tool_result}
        Expected Output: {expected_output}
        
        Validation Criteria:
        1. Tool executed successfully
        2. Result matches expected output format
        3. All required fields present
        4. Data is valid (no errors/nulls)
        
        Return JSON:
        {{
          "test_passed": boolean (true if ALL criteria pass),
          "tool_executed": boolean,
          "format_correct": boolean,
          "fields_present": boolean,
          "data_valid": boolean,
          "reason": "string (explain if test_passed=false)"
        }}
        
        Return ONLY the JSON object.
  model: ${DEFAULT_LLM_MODEL}
  output: [test_results]
  structured_output_dict:
    test_results: dict
  transition: END
```

```bash
mkdir -p suites/my_toolkit/tests
cd suites/my_toolkit

# Create pipeline.yaml with setup/cleanup
# Create README.md with prerequisites
# Create test_case_01_*.yaml in tests/

./run_test.sh --all suites/my_toolkit test_case_01
```

---

## CI/CD Integration

**GitHub Actions**: `.github/workflows/test-runner-reusable.yml`
- Docker execution, auto RCA on failures, HTML reports, artifact upload

**Usage**:
```yaml
jobs:
  test:
    uses: ./.github/workflows/test-runner-reusable.yml
    with:
      test_cases_dir: ado
      environment: dev
    secrets: inherit
```

**Auto RCA**: On failure, runs test-fixer agent for root cause analysis

**Docker**: `ghcr.io/projectalita/alita-sdk:pyodide` with git config fix, dynamic commands via `$DOCKER_COMMAND`

---

## Advanced Topics

**Composable Pipelines**: Reusable YAML fragments (e.g., `composable/rca_on_failure.yaml`)

**Custom RCA**: Edit composable RCA prompts to customize analysis behavior

**Extending**: Add node types in `utils_local.py`, setup types in `setup.py`

---

## Troubleshooting

### Troubleshooting

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError` | `pip install -e '.[all]'` |
| `DEPLOYMENT_URL not set` | Create `.env` |
| `Toolkit not found` | `./run_test.sh --setup` |
| `Pipeline not found` | `./run_test.sh --seed` |
| Test timeout | `--timeout 300` |
| Empty errors (negative tests) | Bug: file report |

**Debug Checklist**: Check logs → Verify .env → Run with `-v` → Try `--local` → Check setup/seed logs → Inspect results.json

---

## Quick Reference

**Commands**:
```bash
./run_all_suites.sh -v ado              # Suite with verbose
./run_test.sh --all suites/ado ADO01    # Full workflow
./run_test.sh --local -v suites/ado ADO01  # Local debug
python scripts/run_suite.py suites/ado --json  # JSON output
```

**Files**: `.env` (config), `suites/<suite>/pipeline.yaml` (suite), `test_results/` (outputs)

**Env Vars**: `DEPLOYMENT_URL`, `API_KEY`, `PROJECT_ID`, `*_TOKEN`, `*_TOOLKIT_ID`

**Results**: `results.json` contains `passed`/`failed`/`error`/`skipped` with assertions

---

## Architecture

**Execution Flow**: Entry → Setup (create toolkits, save IDs) → Seed (upload YAMLs) → Run (execute tests) → Cleanup (delete) → Report (HTML)

**Local Engine** (`utils_local.py`): Builds LangGraph from YAML, executes toolkit/LLM nodes, collects metadata (tokens, timing), handles errors

**Platform API**: `/integrations` (toolkits), `/pipelines` (create/execute), `/executions` (poll status)

---

## Best Practices

**Tests**: One feature per test, descriptive names, validate outputs, `continue_on_error` only for negative tests, clean up artifacts

**Suites**: Document env vars, use `save_to_env`, set timeouts, version configs

**Dev**: Start with `--local`, use `-v` for debug, run `--setup --seed` once, `--seed` after YAML edits, check logs

**Performance**: Skip setup/seed after first run (10x faster), use `--local` (3-10x faster), run suites in parallel with `&`

---

**Framework Version**: 2.0 | **Last Updated**: Feb 2026 | **Maintainer**: Alita SDK Team
