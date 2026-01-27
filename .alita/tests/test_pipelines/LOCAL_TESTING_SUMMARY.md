# Local Testing Quick Reference

## Usage

```bash
# Run specific test locally
./run_test.sh --local <suite> <pattern>

# Run all tests in suite
./run_all_suites.sh --local <suite>

# Python direct
python scripts/run_test.py --local <suite> <pattern>
```

## Required Arguments

| Argument | Description | Example |
|----------|-------------|---------|
| `suite` | Suite folder name | `github_toolkit`, `jira_toolkit` |
| `pattern` | Test name pattern | `list_branches`, `case_01`, `*` |

## Environment Variables

Toolkit credentials are loaded from `.env` using pattern:

```
{TOOLKIT_TYPE}_{FIELD_NAME}
```

### Examples by Toolkit Type

**GitHub:**
```bash
GITHUB_ACCESS_TOKEN=ghp_xxx
GITHUB_BASE_URL=https://api.github.com
```

**JIRA:**
```bash
JIRA_BASE_URL=https://your-instance.atlassian.net
JIRA_USERNAME=your@email.com
JIRA_API_KEY=your_api_key
JIRA_TOKEN=your_pat_token
```

**GitLab:**
```bash
GITLAB_ACCESS_TOKEN=glpat_xxx
GITLAB_BASE_URL=https://gitlab.com
```

**Common (required for all):**
```bash
DEPLOYMENT_URL=https://your-platform.ai/
API_KEY=your_alita_api_key
PROJECT_ID=18
```

## Execution Flow

```
1. Load suite config:     <suite>/pipeline.yaml
2. Execute setup steps:   LocalSetupStrategy creates toolkit tools
3. Build settings:        Uses alita_sdk.configurations to get field names
4. Load credentials:      From .env using {TOOLKIT_TYPE}_{FIELD_NAME}
5. Create tools:          get_tools() from alita_sdk.runtime.toolkits.tools
6. Run tests:             IsolatedPipelineTestRunner.run_test()
```

## Suite Structure

```
<suite>/
├── pipeline.yaml       # Suite config with setup steps
├── configs/
│   └── git-config.json # Toolkit-specific settings
└── tests/
    └── test_case_*.yaml
```

## Missing Required Fields

If a required field is missing, you'll see:

```
======================================================================
ERROR: Missing required configuration for 'jira' toolkit
======================================================================
Configuration class: JiraConfiguration

Missing required fields:

  Field: base_url
    Environment variable: JIRA_BASE_URL
======================================================================
```

## Optional Arguments

| Argument | Description |
|----------|-------------|
| `--dry-run` | Show YAML only |
| `-v` | Verbose output |
