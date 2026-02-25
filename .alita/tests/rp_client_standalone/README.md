# ReportPortal Standalone Client

A lightweight, standalone Python client for reporting test results to ReportPortal without requiring pytest or any other test framework. Perfect for bash-based tests, CI/CD pipelines, or custom test runners.

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Set the following environment variables (or create a `.env` file):

```bash
export RP_ENDPOINT=https://reportportal.example.com/api/receiver
export RP_PROJECT=your-project-uuid
export RP_API_KEY=your-api-key
export RP_LAUNCH=Test Automation  # optional, default launch name
```

Or copy `.env.example` to `.env` and fill in your values.

## Usage

### Python API

```python
from rp_client import ReportPortalClient

with ReportPortalClient() as rp:
    rp.start_launch("My Test Run", description="Running tests")

    suite_id = rp.start_suite("API Tests")
    test_id = rp.start_test("test_endpoint", parent_id=suite_id)

    rp.log(test_id, "Running test...")
    rp.log(test_id, "Success!", level="INFO")
    rp.log(test_id, "Screenshot", attachment="screenshot.png")

    rp.finish_test(test_id, status="PASSED")
    rp.finish_suite(suite_id)
    # launch auto-finishes on context exit
```

### CLI (for bash scripts)

```bash
# Start a launch
LAUNCH=$(python rp_client.py start-launch --name "Bash Tests")

# Start a suite
SUITE=$(python rp_client.py start-suite --launch-id $LAUNCH --name "API Tests")

# Start a test
TEST=$(python rp_client.py start-test --launch-id $LAUNCH --name "test_api" --parent-id $SUITE)

# Log messages
python rp_client.py log --launch-id $LAUNCH --item-id $TEST --message "Running..."
python rp_client.py log --launch-id $LAUNCH --item-id $TEST --message "Error!" --level ERROR

# Attach a file
python rp_client.py log --launch-id $LAUNCH --item-id $TEST --message "Screenshot" --attachment ./screenshot.png

# Finish test
python rp_client.py finish-test --launch-id $LAUNCH --item-id $TEST --status PASSED

# Finish suite
python rp_client.py finish-suite --launch-id $LAUNCH --item-id $SUITE

# Finish launch
python rp_client.py finish-launch --launch-id $LAUNCH
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `start-launch` | Start a new test launch |
| `finish-launch` | Finish a launch |
| `start-suite` | Start a test suite |
| `start-test` | Start a test case |
| `start-item` | Start any item type (SUITE, STEP, etc.) |
| `finish-item` | Finish any item |
| `finish-test` | Finish a test (alias for finish-item) |
| `finish-suite` | Finish a suite (alias for finish-item) |
| `log` | Log a message with optional attachment |

## Status Values

- `PASSED` - Test passed
- `FAILED` - Test failed
- `SKIPPED` - Test was skipped
- `INTERRUPTED` - Test was interrupted
- `CANCELLED` - Test was cancelled

## Log Levels

- `TRACE`
- `DEBUG`
- `INFO`
- `WARN`
- `ERROR`
- `FATAL`

## Attributes

Add custom attributes to launches, suites, or tests:

```bash
# CLI
python rp_client.py start-launch --name "Tests" --attributes env:staging type:smoke

# Python
rp.start_launch("Tests", attributes=[
    {"key": "env", "value": "staging"},
    {"key": "type", "value": "smoke"}
])
```

## File Attachments

Attach screenshots, logs, or any file:

```bash
# CLI
python rp_client.py log --launch-id $LAUNCH --item-id $TEST \
    --message "Screenshot" --attachment ./screenshot.png

# Python
rp.log(test_id, "Screenshot", attachment="screenshot.png")
rp.attach_file(test_id, "output.log", message="Test output")
```

## Example Script

See `example_test.sh` for a complete bash integration example.

## Files

```
rp_client_standalone/
├── rp_client.py      # Main client (Python API + CLI)
├── requirements.txt  # Python dependencies
├── .env.example      # Example configuration
├── example_test.sh   # Example bash script
└── README.md         # This file
```
