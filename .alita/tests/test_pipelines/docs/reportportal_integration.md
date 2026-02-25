# ReportPortal Integration for Alita SDK Test Framework

This integration enables automatic reporting of test results from the Alita SDK test framework to ReportPortal TMS (Test Management System).

## Overview

The integration adds ReportPortal reporting capabilities to the existing test framework without modifying its core functionality:

- **Launch Level**: Entire test suite run becomes a ReportPortal launch
- **Suite Level**: Test suite groups are reported as ReportPortal suites
- **Test Level**: Individual pipeline executions are reported as ReportPortal tests
- **Logging**: Execution details, outputs, and errors are logged to ReportPortal
- **Status Mapping**: Test results (PASSED/FAILED/SKIPPED) are automatically mapped

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     run_suite.py (main)                         │
├─────────────────────────────────────────────────────────────────┤
│  1. Create ReportPortalReporter (optional)                      │
│  2. Start Launch (context manager)                              │
│     │                                                            │
│     ├─► run_suite() or run_suite_local()                        │
│     │   │                                                        │
│     │   ├─► Start Suite                                         │
│     │   │                                                        │
│     │   ├─► For each test:                                      │
│     │   │   ├─► Start Test                                      │
│     │   │   ├─► Execute Pipeline                                │
│     │   │   ├─► Log Result                                      │
│     │   │   └─► Finish Test (PASSED/FAILED/SKIPPED)             │
│     │   │                                                        │
│     │   └─► Finish Suite                                        │
│     │                                                            │
│  3. Finish Launch (auto via context manager)                    │
└─────────────────────────────────────────────────────────────────┘
```

## Configuration

### Environment Variables

Set the following environment variables to enable ReportPortal reporting:

```bash
# Required: Enable ReportPortal
export RP_ENABLED=true

# Required: ReportPortal configuration
export RP_ENDPOINT=https://reportportal.example.com
export RP_PROJECT=your-project-uuid
export RP_API_KEY=your-api-key

# Optional: Customize reporting
export RP_LAUNCH="Alita SDK Tests"      # Default launch name
export RP_MODE=DEFAULT                   # DEFAULT or DEBUG
```

### Using .env File

Create a `.env` file in the test_pipelines directory:

```bash
# .env
RP_ENABLED=true
RP_ENDPOINT=https://reportportal.example.com
RP_PROJECT=alita-sdk-tests
RP_API_KEY=your_api_key_here
RP_LAUNCH=CI/CD Pipeline Tests
RP_MODE=DEFAULT
```

## Usage

### Running Tests with ReportPortal

The integration is **automatic** - just set the environment variables:

```bash
# Enable ReportPortal
export RP_ENABLED=true
export RP_ENDPOINT=https://your-rp.com
export RP_PROJECT=your-project
export RP_API_KEY=your-key

# Run tests as usual
./run_test.sh --all github_toolkit GH01

# Or with run_suite.py
python scripts/run_suite.py github_toolkit --verbose
```

### Local Mode

ReportPortal works with local execution mode too:

```bash
python scripts/run_suite.py github_toolkit --local --verbose
```

### Disabling ReportPortal

To disable ReportPortal (even if configured):

```bash
export RP_ENABLED=false
# or
unset RP_ENABLED
```

## Components

### 1. ReportPortal Client (`rp_client.py`)

Standalone client for ReportPortal API located in `.alita/tests/rp_client_standalone/`:

- Low-level API wrapper
- Supports Python API and CLI usage
- Can be used independently of test framework
- See `rp_client_standalone/README.md` for standalone usage

### 2. Reporter Integration (`rp_reporter.py`)

Integration layer in `scripts/rp_reporter.py`:

- `ReportPortalReporter` class adapts the test framework to ReportPortal
- Wraps `ReportPortalClient` for framework-specific data structures
- Configuration management via environment variables
- Optional and non-intrusive - disabled by default

### 3. Test Framework Integration

Modified files:
- `scripts/run_suite.py` - Added reporter parameter to `run_suite()` and `run_suite_local()`
- Sequential execution fully supported with detailed logging
- Parallel execution support (basic - no per-test logging in parallel mode yet)

## Features

### Supported

✅ **Suite Execution**: Full suite reporting with aggregate statistics  
✅ **Individual Test Reporting**: Each pipeline/test reported separately  
✅ **Status Mapping**: PASSED/FAILED/SKIPPED/ERROR statuses  
✅ **Execution Logs**: Output and error logs attached to tests  
✅ **Execution Time**: Timing information for each test  
✅ **Local Mode**: Works with `--local` flag  
✅ **Remote Mode**: Works with platform API execution  
✅ **Sequential Execution**: Full logging support  

### Limitations

⚠️ **Parallel Execution**: Basic support - individual test logs not captured during parallel execution  
⚠️ **File Attachments**: Not yet implemented (screenshots, artifacts, etc.)  
⚠️ **Post-Test Hooks**: Hook results logged but not as separate items  

## Troubleshooting

### Reporter Not Starting

Check the logs with `--verbose`:

```bash
python scripts/run_suite.py github_toolkit --verbose
```

Common issues:
- Missing environment variables (RP_ENDPOINT, RP_PROJECT, RP_API_KEY)
- `RP_ENABLED` not set to `true`
- ReportPortal client dependencies not installed

### Installing Dependencies

```bash
# Install ReportPortal client dependencies
cd .alita/tests/rp_client_standalone
pip install -r requirements.txt
```

### Checking Configuration

Run with verbose flag to see configuration status:

```bash
python scripts/run_suite.py github_toolkit --verbose
# Look for: "ReportPortal reporting enabled" or "disabled"
```

### Testing ReportPortal Connection

Test the standalone client directly:

```bash
cd .alita/tests/rp_client_standalone
python rp_client.py start-launch --name "Connection Test"
# Should print a launch UUID if successful
```

## Examples

### Basic Test Suite Reporting

```bash
# Run GitHub toolkit tests with ReportPortal
export RP_ENABLED=true
export RP_ENDPOINT=https://rp.example.com
export RP_PROJECT=my-project
export RP_API_KEY=abc123...

python scripts/run_suite.py github_toolkit
```

### CI/CD Integration

```yaml
# .github/workflows/tests.yml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: Run Tests
        env:
          RP_ENABLED: true
          RP_ENDPOINT: ${{ secrets.RP_ENDPOINT }}
          RP_PROJECT: ${{ secrets.RP_PROJECT }}
          RP_API_KEY: ${{ secrets.RP_API_KEY }}
          RP_LAUNCH: "CI Build #${{ github.run_number }}"
        run: |
          python scripts/run_suite.py github_toolkit --exit-code
```

### Multiple Suites

```bash
# Report multiple suites to same launch
export RP_ENABLED=true
export RP_LAUNCH="Nightly Regression"

python scripts/run_suite.py github_toolkit
python scripts/run_suite.py jira_toolkit
python scripts/run_suite.py confluence_toolkit
```

## Development

### Adding ReportPortal Support to New Test Types

If you add new test execution paths, follow this pattern:

```python
from rp_reporter import create_reporter

# In your execution function
def run_my_tests(tests, logger=None, reporter=None):
    # Start suite
    rp_suite_id = None
    if reporter and reporter.active:
        rp_suite_id = reporter.start_suite("My Suite")
    
    for test in tests:
        # Start test
        rp_test_id = None
        if reporter and reporter.active:
            rp_test_id = reporter.start_test(
                test.name, 
                parent_id=rp_suite_id
            )
        
        # Execute test
        result = execute_test(test)
        
        # Report result
        if reporter and reporter.active and rp_test_id:
            reporter.log_result(rp_test_id, result)
            reporter.finish_test(rp_test_id, result)
    
    # Finish suite
    if reporter and reporter.active and rp_suite_id:
        reporter.finish_suite(rp_suite_id, "PASSED")
```

### Testing the Integration

1. **Unit Test**: Test reporter creation and configuration
2. **Integration Test**: Run a small suite with ReportPortal enabled
3. **Verification**: Check ReportPortal UI for reported results

## References

- [ReportPortal Documentation](https://reportportal.io/docs)
- [Alita SDK Test Framework](../README.md)
- [Standalone Client README](../../rp_client_standalone/README.md)

## Future Enhancements

- [ ] File attachment support (screenshots, logs, artifacts)
- [ ] Enhanced parallel execution logging
- [ ] Hook results as nested test items
- [ ] Retry/rerun reporting
- [ ] Test attributes and tags from YAML metadata
- [ ] Custom launch attributes from config
- [ ] Real-time log streaming during execution
- [ ] Failed test screenshot capture
