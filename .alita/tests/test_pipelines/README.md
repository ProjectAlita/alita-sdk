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
