# Test Pipelines Framework

Comprehensive test automation framework for Alita SDK toolkits and features using declarative pipeline definitions.

## Directory Structure

```
test_pipelines/
├── README.md                    # This file
├── run_all_suites.sh           # Automated execution of all suites (recommended)
├── run_test.sh                 # Run individual tests (development)
├── .env                        # Environment configuration (generated)
├── scripts/                    # Python implementation scripts
│   ├── setup.py               # Setup test environments
│   ├── seed_pipelines.py      # Seed test pipelines to platform
│   ├── run_suite.py           # Execute test suites
│   ├── cleanup.py             # Clean up test artifacts
│   └── delete_pipelines.py    # Delete pipelines utility
├── composable/                  # Shared reusable pipeline components
│   ├── README.md               # Composable pipelines documentation
│   └── rca_on_failure.yaml     # RCA with SDK code search
├── configs/                     # Shared configuration files
│   └── git-config.json         # GitHub toolkit base config
├── github_toolkit/             # GitHub toolkit integration tests
│   ├── README.md
│   ├── pipeline.yaml           # Suite configuration
│   ├── tests/                  # Test case files
│   │   ├── test_case_1_*.yaml
│   │   ├── test_case_2_*.yaml
│   │   └── ...
│   └── configs/                # Suite-specific configs (if needed)
├── state_retrieval/            # Pipeline state management tests
│   ├── pipeline.yaml
│   └── tests/
└── structured_output/          # LLM structured output tests
    ├── pipeline.yaml
    └── tests/
```

## Test Suites

### github_toolkit

Integration tests for GitHub toolkit functionality covering both read and write operations.

**Features Tested**:
- Branch operations (list, create, delete)
- Issue management (create, read, update, list)
- Pull request workflows
- Repository operations (search, get info)
- File operations (read, write, push)

**Requirements**:
- GitHub access token with repo permissions
- Test repository (default: ProjectAlita/elitea-testing)
- Two toolkits: main GitHub toolkit + SDK analysis toolkit (for RCA)

**Configuration**: See `github_toolkit/pipeline.yaml`

### state_retrieval

Tests for pipeline state management and data persistence across nodes.

**Features Tested**:
- State variable initialization and updates
- State retrieval from previous nodes
- State persistence across node transitions
- Complex state transformations
- State validation and type checking

**Requirements**:
- GitHub access token (for SDK analysis toolkit)
- SDK analysis toolkit (for RCA with code search)

**Configuration**: See `state_retrieval/pipeline.yaml`

### structured_output

Tests for LLM structured output functionality and type handling.

**Features Tested**:
- JSON schema validation
- Pydantic model outputs
- Complex nested structures
- Type coercion and validation
- Error handling for invalid outputs

**Requirements**:
- GitHub access token (for SDK analysis toolkit)
- SDK analysis toolkit (for RCA with code search)

**Configuration**: See `structured_output/pipeline.yaml`

## Pipeline Configuration (pipeline.yaml)

Each test suite has a `pipeline.yaml` file that defines:

### Basic Structure

```yaml
name: suite_name
description: Suite description

# Setup steps - executed before tests
setup:
  - name: Setup Step Name
    type: toolkit|configuration|toolkit_invoke
    config:
      # Step-specific configuration
    save_to_env:
      - key: ENV_VAR_NAME
        value: $.json.path

# Composable pipelines - seeded first, used by hooks
composable_pipelines:
  - file: ../composable/rca_on_failure.yaml
    env:
      SUITE_NAME: ${SUITE_NAME}
      RCA_MODEL: ${RCA_MODEL:gpt-4o-mini}
    save_to_env:
      - key: RCA_PIPELINE_ID
        value: $.id

# Test execution configuration
execution:
  test_directory: tests
  order:
    - test_case_1_*.yaml
    - test_case_2_*.yaml
  substitutions:
    VAR_NAME: ${VAR_VALUE}
  settings:
    timeout: 120
    parallel: 1
    stop_on_failure: false

# Hooks - automated actions at different stages
hooks:
  post_test:
    - name: rca_on_failure
      pipeline_id: ${RCA_PIPELINE_ID}
      condition: "result.get('test_passed') is False"
      input_mapping:
        test_name: "result.get('pipeline_name', 'Unknown')"
      output_mapping:
        "result['rca']": "rca_result"

# Cleanup steps - executed after tests
cleanup:
  - name: Cleanup Step Name
    type: toolkit|pipeline
    config:
      # Cleanup configuration
    continue_on_error: true
```

### Setup Steps

Setup steps prepare the test environment by creating toolkits, configurations, and test data.

**Types**:

1. **configuration** - Create platform configurations (e.g., GitHub credentials)
   ```yaml
   - name: Setup GitHub Configuration
     type: configuration
     config:
       config_type: github
       alita_title: github
       data:
         access_token: ${GIT_TOOL_ACCESS_TOKEN}
   ```

2. **toolkit** - Create or update toolkits
   ```yaml
   - name: Create GitHub Toolkit
     type: toolkit
     action: create_or_update
     config:
       config_file: configs/git-config.json
       toolkit_type: github
       overrides:
         repository: ${GITHUB_TEST_REPO}
       toolkit_name: testing
     save_to_env:
       - key: GITHUB_TOOLKIT_ID
         value: $.id
   ```

3. **toolkit_invoke** - Invoke toolkit tools for setup
   ```yaml
   - name: Create Test Branch
     type: toolkit_invoke
     config:
       toolkit_id: ${GITHUB_TOOLKIT_ID}
       tool_name: create_branch
       tool_params:
         branch_name: tc-test-${TIMESTAMP}
     save_to_env:
       - key: GITHUB_TEST_BRANCH
         value: $.result.branch_name
   ```

### Composable Pipelines

Composable pipelines are reusable pipeline components that can be invoked conditionally via hooks.

```yaml
composable_pipelines:
  - file: ../composable/rca_with_code_analysis.yaml
    env:
      SUITE_NAME: github_toolkit
      RCA_MODEL: ${RCA_MODEL:gpt-4o-mini}
      SDK_TOOLKIT_ID: ${SDK_TOOLKIT_ID}
    save_to_env:
      - key: RCA_PIPELINE_ID
        value: $.id
```

**Available Composables**: See `composable/README.md`

### Hooks

Hooks are automated actions triggered at different stages of test execution.

**Hook Types**:
- `pre_setup` - Before setup steps
- `post_setup` - After setup completes
- `post_test` - After each test (for RCA, logging, etc.)
- `pre_cleanup` - Before cleanup
- `post_cleanup` - After cleanup

**Example: RCA on Failure**
```yaml
hooks:
  post_test:
    - name: rca_on_failure
      pipeline_id: ${RCA_PIPELINE_ID}
      condition: "result.get('test_passed') is False"
      input_mapping:
        test_name: "result.get('pipeline_name', 'Unknown')"
        test_results: "result"
      output_mapping:
        "result['rca']": "rca_result"
        "result['rca_summary']": "rca_summary"
```

**Input Mapping**: Maps test result fields to pipeline input parameters using Python expressions
**Output Mapping**: Maps pipeline output back to test result using assignment expressions
**Condition**: Python expression evaluated to determine if hook should run

### Cleanup Steps

Cleanup steps remove test artifacts after test execution.

```yaml
cleanup:
  - name: Delete Test Branch
    type: toolkit_invoke
    config:
      toolkit_id: ${GITHUB_TOOLKIT_ID}
      tool_name: delete_branch
      tool_params:
        branch_name: ${GITHUB_TEST_BRANCH}
    continue_on_error: true

  - name: Delete Test Pipelines
    type: pipeline
    config:
      pattern: "GH*"
    continue_on_error: true

  - name: Delete Test Toolkit
    type: toolkit
    config:
      toolkit_id: ${GITHUB_TOOLKIT_ID}
    continue_on_error: true
```

## Test Case Files

Test cases are defined as pipeline YAML files in the suite's `tests/` directory.

### Basic Structure

```yaml
name: "Test Case Name"
description: "What this test validates"

# Variables available in pipeline
state:
  toolkit_id:
    type: int
  result:
    type: dict

# First node executed
entry_point: invoke_tool

nodes:
  - id: invoke_tool
    type: toolkit
    toolkit_id: ${GITHUB_TOOLKIT_ID}
    tool_name: list_branches
    tool_params:
      repository: ProjectAlita/elitea-testing
    output:
      - result
    transition: validate_result

  - id: validate_result
    type: code
    code:
      type: fixed
      value: |
        tool_result = alita_state.get('result', {})

        # Validation logic
        test_passed = len(tool_result.get('branches', [])) > 0

        # Return test results
        {
            "test_passed": test_passed,
            "output": tool_result,
            "error": None if test_passed else "No branches found"
        }
    output:
      - result
    transition: END
```

### Node Types

1. **toolkit** - Invoke toolkit tools
2. **llm** - LLM calls with optional tools
3. **code** - Python code execution
4. **condition** - Conditional branching
5. **human** - Human input (not used in automated tests)

### Test Results Format

All test cases must return a result dict with:

```python
{
    "test_passed": bool,      # Whether test passed
    "output": dict,           # Tool/operation output
    "error": str | None,      # Error message if failed
    # ... additional test-specific fields
}
```

## Scripts

### setup.py

Executes setup steps from `pipeline.yaml` to prepare the test environment.

```bash
# Run setup for a specific suite
python scripts/setup.py github_toolkit

# With verbose output
python scripts/setup.py github_toolkit --verbose

# Save environment to file
python scripts/setup.py github_toolkit --output-env .env
```

**What it does**:
1. Loads `pipeline.yaml` from suite directory
2. Executes each setup step in order
3. Saves environment variables from `save_to_env` mappings
4. Stops on first error (unless `continue_on_error: true`)

### seed_pipelines.py

Seeds test pipelines and composables to the platform.

```bash
# Seed all tests for a suite
python scripts/seed_pipelines.py github_toolkit

# Seed with GitHub toolkit ID
python scripts/seed_pipelines.py github_toolkit --github-toolkit-id 123

# Verbose output
python scripts/seed_pipelines.py github_toolkit --verbose

# Dry run (validate only)
python scripts/seed_pipelines.py github_toolkit --dry-run
```

**What it does**:
1. Loads `pipeline.yaml` and test case files from `tests/`
2. Seeds composable pipelines first (for hooks)
3. Links toolkits to composable pipelines
4. Seeds test case pipelines with environment substitutions
5. Returns list of seeded pipeline IDs

**Environment Substitution**:
- `${GITHUB_TOOLKIT_ID}` - From setup or command line
- `${SDK_TOOLKIT_ID}` - From .env file
- `${SUITE_NAME}` - Derived from folder name
- `${TIMESTAMP}` - Current timestamp
- Custom variables from setup `save_to_env`

### run_suite.py

Executes test suite and generates results.

```bash
# Run entire suite
python scripts/run_suite.py github_toolkit

# Run specific test
python scripts/run_suite.py github_toolkit --pattern "test_case_1_*"

# With verbose output
python scripts/run_suite.py github_toolkit --verbose

# JSON output
python scripts/run_suite.py github_toolkit --json

# Save results to file
python scripts/run_suite.py github_toolkit --json > results.json

# Stop on first failure
python scripts/run_suite.py github_toolkit --fail-fast
```

**What it does**:
1. Loads seeded pipeline IDs from environment
2. Executes each test pipeline via platform API
3. Waits for completion with polling
4. Invokes post_test hooks for each test (e.g., RCA on failure)
5. Collects and formats results
6. Generates summary with pass/fail counts

**Output Format**:
```json
{
  "suite_name": "github_toolkit",
  "total_tests": 10,
  "passed": 8,
  "failed": 2,
  "duration": 123.45,
  "tests": [
    {
      "name": "GH-TC1-list-branches",
      "test_passed": true,
      "duration": 5.2,
      "output": {...}
    },
    {
      "name": "GH-TC2-create-issue",
      "test_passed": false,
      "error": "Validation failed",
      "rca": {
        "root_cause": "...",
        "category": "assertion_failed",
        "severity": "medium"
      }
    }
  ]
}
```

### cleanup.py

Removes test artifacts after execution.

```bash
# Run cleanup for a suite (will prompt for confirmation)
python scripts/cleanup.py github_toolkit

# Skip confirmation prompt
python scripts/cleanup.py github_toolkit --yes

# With verbose output
python scripts/cleanup.py github_toolkit --verbose --yes

# Dry run to see what would be deleted
python scripts/cleanup.py github_toolkit --dry-run
```

**What it does**:
1. Loads cleanup steps from `pipeline.yaml`
2. Executes each cleanup step in order
3. Continues on errors (logged but doesn't stop)
4. Deletes toolkits, pipelines, branches, etc.

### run_all_suites.sh

Automated execution of all test suites with full workflow (initial cleanup, setup, seed, run, cleanup).

**Requirements**: Bash 4.0+ (macOS ships with bash 3.2, install with `brew install bash`)

```bash
# On macOS, install bash 4+ first
brew install bash

# Run all suites (recommended)
./run_all_suites.sh

# Or explicitly use bash 4+
bash ./run_all_suites.sh

# Run specific suites only
./run_all_suites.sh github_toolkit state_retrieval

# With verbose output
./run_all_suites.sh -v

# Skip initial cleanup (faster but may have conflicts)
./run_all_suites.sh --skip-initial-cleanup

# Keep resources after tests for debugging
./run_all_suites.sh --skip-cleanup

# Stop on first failure
./run_all_suites.sh --stop-on-failure

# Custom output directory
./run_all_suites.sh -o my_results

# Development mode (no cleanup at all)
./run_all_suites.sh --skip-initial-cleanup --skip-cleanup

# Show help
./run_all_suites.sh --help
```

**What it does**:
1. **Initial Cleanup**: Removes leftover resources from previous runs (can be skipped with `--skip-initial-cleanup`)
2. **Setup**: Executes setup steps for each suite
3. **Seed**: Seeds composable and test pipelines
4. **Run**: Executes all tests with RCA on failures
5. **Cleanup**: Removes test artifacts (can be skipped with `--skip-cleanup`)

**Features**:
- Color-coded progress output (green=success, red=error, yellow=warning)
- Duration tracking per suite and total
- Comprehensive logging (all logs saved to `test_results/<suite>/`)
- Summary table with pass/fail counts
- Exit code 0 if all passed, 1 if any failed
- Flexible execution control with multiple flags

**Output Structure**:
```
test_results/
├── github_toolkit/
│   ├── setup.log
│   ├── seed.log
│   ├── run.log
│   ├── cleanup.log
│   └── results.json
├── state_retrieval/
│   └── ...
└── structured_output/
    └── ...
```

**Recommended Usage**:
- Use default settings for CI/CD: `./run_all_suites.sh`
- Use `--skip-initial-cleanup` for faster re-runs if environment is known to be clean
- Use `--skip-cleanup` when debugging test failures (keeps resources for inspection)
- Use `--stop-on-failure` in development to fail fast

## Environment Variables

Create `.env` file in the test_pipelines directory or project root:

```bash
# Platform connection
DEPLOYMENT_URL=https://dev.elitea.ai
API_KEY=your_api_key
PROJECT_ID=2

# GitHub toolkit
GIT_TOOL_ACCESS_TOKEN=ghp_xxxxxxxxxxxx
GITHUB_TEST_REPO=ProjectAlita/elitea-testing
GITHUB_BASE_BRANCH=main
GITHUB_SECRET_NAME=github
GITHUB_TOOLKIT_NAME=testing

# SDK analysis toolkit (for RCA with code search)
SDK_REPO=ProjectAlita/alita-sdk
SDK_BRANCH=main
SDK_TOOLKIT_ID=    # Set after setup
SDK_TOOLKIT_NAME=sdk-analysis

# RCA configuration
RCA_MODEL=gpt-4o-mini
```

## Complete Workflow

### Automated Workflow (Recommended)

The simplest way to run test suites is using the automated script.

**Requirements**: Bash 4.0+ (macOS users: `brew install bash`)

```bash
cd alita-sdk/.alita/tests/test_pipelines

# Create .env file with required variables
cp .env.example .env
# Edit .env with your values

# On macOS, install bash 4+ first (if needed)
brew install bash

# Run all suites with full workflow
./run_all_suites.sh

# Or run specific suites
./run_all_suites.sh github_toolkit state_retrieval

# With verbose output for debugging
./run_all_suites.sh -v
```

This automatically handles:
1. Initial cleanup (removes leftovers from previous runs)
2. Setup (creates toolkits and test environment)
3. Seed (seeds pipelines to platform)
4. Run (executes tests with RCA)
5. Cleanup (removes test artifacts)

Results are saved to `test_results/` directory with comprehensive logs.

### Manual Step-by-Step Workflow

For more control or debugging, run each step individually:

#### 1. Setup Environment

```bash
cd alita-sdk/.alita/tests/test_pipelines

# Create .env file with required variables
cp .env.example .env
# Edit .env with your values

# Run setup and save environment variables
python scripts/setup.py github_toolkit --output-env .env

# Verify toolkit IDs are saved
cat .env | grep TOOLKIT_ID
```

#### 2. Seed Pipelines

```bash
# Seed all test pipelines
python scripts/seed_pipelines.py github_toolkit

# Verify pipelines on platform UI
# Check that composable pipelines have toolkits linked
```

#### 3. Run Tests

```bash
# Execute test suite
python scripts/run_suite.py github_toolkit --verbose

# Save results to JSON file
python scripts/run_suite.py github_toolkit --json > test_results.json

# Review results
cat test_results.json

# Check RCA for failures (with JSON output)
python scripts/run_suite.py github_toolkit --json | python -c "import sys,json; data=json.load(sys.stdin); [print(f'{t[\"name\"]}: {t.get(\"rca_summary\", \"no RCA\")}') for t in data.get('tests', []) if not t.get('test_passed')]"
```

#### 4. Cleanup

```bash
# Remove test artifacts (with confirmation)
python scripts/cleanup.py github_toolkit

# Remove test artifacts (skip confirmation)
python scripts/cleanup.py github_toolkit --yes

# Verify cleanup
# - Test branches deleted
# - Test pipelines deleted
# - Toolkits deleted (optional)
```

## Creating a New Test Suite

### 1. Create Suite Directory

```bash
cd test_pipelines
mkdir my_new_suite
cd my_new_suite
mkdir tests configs
```

### 2. Create pipeline.yaml

```yaml
name: my_new_suite
description: Tests for my feature

setup:
  # Define setup steps

composable_pipelines:
  # Choose RCA variant based on needs
  - file: ../composable/rca_on_failure.yaml
    env:
      SUITE_NAME: my_new_suite
      RCA_MODEL: ${RCA_MODEL:gpt-4o-mini}
    save_to_env:
      - key: RCA_PIPELINE_ID
        value: $.id

execution:
  test_directory: tests
  order:
    - test_case_*.yaml
  settings:
    timeout: 120
    parallel: 1

hooks:
  post_test:
    - name: rca_on_failure
      pipeline_id: ${RCA_PIPELINE_ID}
      condition: "result.get('test_passed') is False"
      input_mapping:
        test_name: "result.get('pipeline_name', 'Unknown')"
        test_results: "result"
      output_mapping:
        "result['rca']": "rca_result"

cleanup:
  # Define cleanup steps
```

### 3. Create Test Cases

Create test files in `tests/` directory:

```yaml
# tests/test_case_1_basic.yaml
name: "MyFeature-TC1-basic"
description: "Test basic functionality"

state:
  result:
    type: dict

entry_point: test_operation

nodes:
  - id: test_operation
    type: code
    code:
      value: |
        # Test logic here
        test_passed = True
        {
            "test_passed": test_passed,
            "output": {},
            "error": None
        }
    output:
      - result
    transition: END
```

### 4. Test Locally

```bash
# Run setup
python ../scripts/setup.py my_new_suite --save-env

# Seed pipelines
python ../scripts/seed_pipelines.py my_new_suite

# Run tests
python ../scripts/run_suite.py my_new_suite --verbose

# Cleanup
python ../scripts/cleanup.py my_new_suite
```

### 5. Document

Create `README.md` in your suite directory documenting:
- What features are tested
- Prerequisites and setup requirements
- Test case descriptions
- Known issues or limitations

## Best Practices

### Test Organization

- **One feature per test case**: Each test should validate a single feature or operation
- **Clear naming**: Use `test_case_N_feature_name.yaml` pattern
- **Execution order**: Number tests to control execution order (1-10, not 01-10 for sorting)
- **Descriptive names**: Pipeline name should identify the test (e.g., "GH-TC1-list-branches")

### Test Design

- **Validate outputs**: Always check tool results, don't assume success
- **Clear pass/fail**: Return explicit `test_passed: bool`
- **Error messages**: Provide descriptive error messages for failures
- **Idempotent**: Tests should be runnable multiple times
- **Isolated**: Tests shouldn't depend on each other's side effects

### Configuration

- **Use composables**: Leverage shared RCA pipelines instead of duplicating
- **Environment variables**: Use ${VAR} pattern for reusable configs
- **Defaults**: Provide sensible defaults for optional variables
- **Documentation**: Comment complex substitutions or mappings

### Hooks

- **Conditions**: Use clear, simple condition expressions
- **Input mapping**: Map only necessary fields to reduce noise
- **Output mapping**: Choose meaningful result field names
- **Performance**: Hooks add overhead, use judiciously

### Cleanup

- **continue_on_error**: Always set to true for cleanup steps
- **Order**: Clean up in reverse order of creation
- **Verification**: Log what was deleted for debugging
- **Optional**: Make toolkit deletion optional (may want to reuse)

## Troubleshooting

### Setup Failures

**Problem**: Toolkit creation fails with validation error
```
Solution: Check that config file doesn't contain conflicting fields
Example: Remove github_configuration from git-config.json if using overrides
```

**Problem**: Setup completes but IDs not saved
```
Solution: Check save_to_env mappings use correct JSON paths ($.id, $.result.name)
```

### Seeding Failures

**Problem**: Environment variables not substituted
```
Solution: Verify variables exist in .env or are passed via command line
Check: python scripts/seed_pipelines.py --verbose to see substitution values
```

**Problem**: Composable pipeline not linked to toolkit
```
Solution: Ensure toolkit_ids field is set in pipeline data
Check: API logs show toolkit linking attempt
```

### Execution Failures

**Problem**: Pipeline execution times out
```
Solution: Increase timeout in pipeline.yaml execution.settings.timeout
Check: Platform logs for actual execution time
```

**Problem**: RCA output not appearing in results
```
Solution: Verify format_output node uses output: [messages] not state variables
Check: Hook output_mapping targets correct result fields
```

**Problem**: Test fails but no error message
```
Solution: Ensure validation node returns error field with descriptive message
```

### Cleanup Issues

**Problem**: Cleanup fails to delete resources
```
Solution: Enable verbose mode to see which step fails
Check: Resource IDs are correct and saved from setup
```

**Problem**: Branch deletion fails
```
Solution: Verify branch name matches what was created
Check: Repository settings allow branch deletion
```

## Advanced Topics

### Custom Composables

Create suite-specific composable pipelines in `composables/` directory for reusable logic like:
- Data validation patterns
- Common tool invocation sequences
- Result transformation pipelines

Reference: `composable/README.md`

### Parallel Execution

```yaml
execution:
  settings:
    parallel: 3  # Run up to 3 tests concurrently
```

**Considerations**:
- Tests must be independent (no shared state)
- Resource limits (API rate limits, platform capacity)
- Cleanup complexity (parallel resource creation)

### Conditional Test Execution

Use `enabled` field to conditionally run tests:

```yaml
- name: Optional Test Step
  type: toolkit_invoke
  enabled: ${RUN_OPTIONAL_TESTS:false}
```

### Custom Environment Loaders

Add custom environment loaders in seed_pipelines.py for specialized variable resolution:

```python
def load_custom_var_from_env():
    """Load custom variable with validation."""
    value = load_from_env("CUSTOM_VAR")
    if value:
        # Custom validation/transformation
        return transform(value)
    return None
```

## Resources

- **Composable Pipelines**: `composable/README.md`
- **GitHub Toolkit Tests**: `github_toolkit/README.md`
- **Pipeline Schema**: Contact platform team for JSON schema
- **API Documentation**: https://dev.elitea.ai/api/docs

## Contributing

When adding new test suites:

1. Follow the established directory structure
2. Use shared composables where possible
3. Document prerequisites and setup requirements
4. Add test case descriptions to suite README
5. Verify all scripts work with your suite
6. Test complete workflow (setup → seed → run → cleanup)

## Support

For issues or questions:
- Check troubleshooting section above
- Review existing test suites for examples
- Check platform logs for detailed errors
- Contact the Alita SDK team
