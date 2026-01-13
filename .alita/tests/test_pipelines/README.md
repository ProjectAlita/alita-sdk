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

## Scripts

| Script | Purpose |
|--------|---------|
| `seed_pipelines.py` | Deploy pipeline YAML files to platform |
| `delete_pipelines.py` | Remove pipelines from platform |
| `run_pipeline.py` | Execute single pipeline and get results |
| `run_suite.py` | Execute multiple pipelines with aggregated results |

## Seeding Pipelines

Deploy test cases from a folder to the platform:

```bash
# Basic usage
python seed_pipelines.py github_toolkit

# With options
python seed_pipelines.py github_toolkit \
  --base-url http://192.168.68.115 \
  --project-id 2 \
  --github-toolkit-id 71 \
  -v

# Dry run (preview without creating)
python seed_pipelines.py github_toolkit --dry-run
```

## Deleting Pipelines

Remove pipelines before reseeding:

```bash
# Delete by ID range
python delete_pipelines.py --range 267-286

# Delete by pattern
python delete_pipelines.py --pattern "GH*"

# Delete specific IDs
python delete_pipelines.py --ids 287 288 289

# List pipelines (no delete)
python delete_pipelines.py --list

# Dry run
python delete_pipelines.py --range 267-286 --dry-run
```

## Executing Tests

### Single Pipeline

```bash
# By ID
python run_pipeline.py 287

# By name
python run_pipeline.py --name "GH1 - List Branches"

# With options
python run_pipeline.py 287 -v --timeout 180

# JSON output (for scripting)
python run_pipeline.py 287 --json

# Exit code based on test result (0=pass, 1=fail)
python run_pipeline.py 287 --exit-code
```

### Test Suite

```bash
# Run by pattern
python run_suite.py --pattern "GH*"

# Run multiple patterns
python run_suite.py --pattern "GH1*" --pattern "GH2*"

# Run specific IDs
python run_suite.py --ids 287 288 289

# Run from folder
python run_suite.py github_toolkit

# Parallel execution
python run_suite.py --pattern "GH*" --parallel 4

# JSON output
python run_suite.py --pattern "GH*" --json
```

## Output Examples

### Successful Test
```
============================================================
Pipeline: GH1 - List Branches (ID: 288)
Version: 304
Status: PASSED
Execution Time: 6.40s

Output:
{
  "result": {
    "test_passed": true,
    "branches_count": 87,
    ...
  }
}
============================================================
```

### Suite Summary
```
============================================================
Suite: Pattern: GH*
============================================================
Total: 10 | Passed: 10 | Failed: 0 | Errors: 0
Success Rate: 100.0%
Execution Time: 65.07s
============================================================

Results:
  ✓ GH1 - List Branches (6.4s)
  ✓ GH2 - Set Active Branch (5.7s)
  ✗ GH8 - Create Branch (7.6s)
      Error: Unable to create branch due to error: 422 {"message": "refs/heads/...
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AUTH_TOKEN` / `ELITEA_TOKEN` / `API_KEY` | Bearer token for authentication | - |
| `BASE_URL` / `DEPLOYMENT_URL` | Platform URL | `http://192.168.68.115` |
| `PROJECT_ID` | Target project ID | `2` |
| `GITHUB_TOOLKIT_ID` | GitHub toolkit ID for test cases | - |
| `GITHUB_TOOLKIT_NAME` | GitHub toolkit name | `testing` |

Or create a `.env` file:
```
AUTH_TOKEN=your_api_key_here
BASE_URL=http://192.168.68.115
PROJECT_ID=2
GITHUB_TOOLKIT_ID=71
GITHUB_TOOLKIT_NAME=testing
```

## Creating Test Cases

Test cases are YAML files in subfolders (e.g., `github_toolkit/`):

```yaml
name: "GH1 - List Branches"
description: "Verify list_branches tool returns repository branches"

toolkits:
  - id: ${GITHUB_TOOLKIT_ID}
    name: ${GITHUB_TOOLKIT_NAME}

state:
  input:
    type: str
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
        test_results = {
            "test_passed": result is not None and len(result) > 0,
            "branches_count": len(result) if result else 0
        }
        test_results
    input:
      - tool_result
    output:
      - messages
    structured_output: false
    transition: END
```

### Key Points

1. **Variables**: Use `${VAR_NAME}` for substitution during seeding
2. **Code nodes**: Last expression is the return value
3. **test_passed**: Include this field in results for pass/fail detection
4. **structured_output**: Use `false` for single value, `true` for dict returns

## Typical Workflow

```bash
# 1. Edit YAML test cases
vim github_toolkit/test_case_8_create_branch.yaml

# 2. Delete old pipelines
python delete_pipelines.py --pattern "GH*" --yes

# 3. Seed updated pipelines
python seed_pipelines.py github_toolkit -v

# 4. Run tests
python run_suite.py --pattern "GH*"

# 5. Debug failures
python run_pipeline.py --name "GH8 - Create Branch" -v
```
