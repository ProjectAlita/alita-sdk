# alita-cli Quick Reference

## Installation
```bash
cd alita-sdk
pip install -e ".[cli]"
```

## Setup Authentication
```bash
cat > .env <<EOF
DEPLOYMENT_URL=https://api.elitea.ai
PROJECT_ID=123
API_KEY=your_api_key
EOF
```

## Essential Commands

### Configuration
```bash
alita-cli config                     # Show configuration
alita-cli --debug config             # Debug mode
alita-cli --output json config       # JSON output
```

### Toolkits
```bash
alita-cli toolkit list               # List all toolkits
alita-cli toolkit schema jira        # Show schema
alita-cli toolkit tools jira         # List tools
```

### Testing
```bash
# Basic test
alita-cli toolkit test jira \
    --tool get_issue \
    --config jira-config.json \
    --param issue_key=PROJ-123

# Multiple params
alita-cli toolkit test github \
    --tool get_issue \
    --config github-config.json \
    --param owner=user \
    --param repo=myrepo \
    --param issue_number=42

# Custom LLM
alita-cli toolkit test jira \
    --tool search_issues \
    --config jira-config.json \
    --param jql="project = PROJ" \
    --llm-model gpt-4o \
    --temperature 0.7

# JSON output
alita-cli --output json toolkit test jira \
    --tool get_issue \
    --config jira-config.json \
    --param issue_key=PROJ-123 | jq '.'
```

## Config File Example
```json
{
  "base_url": "https://jira.company.com",
  "cloud": true,
  "jira_configuration": {
    "username": "user@company.com",
    "api_key": "your_api_key"
  }
}
```

## Common Options
```bash
--env-file PATH          # Use different .env file
--debug                  # Enable debug logging
--output [text|json]     # Output format
```

## Scripting Example
```bash
#!/bin/bash
result=$(alita-cli --output json toolkit test jira \
    --tool get_issue \
    --config jira-config.json \
    --param issue_key=PROJ-123)

if echo "$result" | jq -e '.success' > /dev/null; then
    echo "✓ Test passed"
    echo "$result" | jq -r '.result'
else
    echo "✗ Test failed: $(echo "$result" | jq -r '.error')"
    exit 1
fi
```

## Get Help
```bash
alita-cli --help                     # General help
alita-cli toolkit --help             # Toolkit commands
alita-cli toolkit test --help        # Test command options
@sdk-dev /cli-testing                # Copilot prompt
```

## Documentation
- **Quick start**: `CLI_GUIDE.md`
- **Complete guide**: `.github/prompts/cli-testing.prompt.md`
- **Agent help**: `@sdk-dev`

## Troubleshooting

**Missing config?**
```bash
alita-cli config  # Check what's missing
```

**Toolkit not found?**
```bash
alita-cli toolkit list  # See available
```

**Tool not found?**
```bash
alita-cli toolkit tools jira --config jira-config.json
```

**Debug issues?**
```bash
alita-cli --debug toolkit test ...
```
