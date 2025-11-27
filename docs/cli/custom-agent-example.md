# Example: Custom Development Agent

This example shows how to create and use a custom agent for your development workflow using environment variables and toolkit configurations.

## Setup Environment Variables

Create `.env` file:

```bash
# Alita Platform
DEPLOYMENT_URL=https://your-deployment.alita.ai
PROJECT_ID=12345
API_KEY=your_api_key

# Agent configuration
AGENTS_DIR=.github/agents

# Project context
PROJECT_NAME=MyAwesomeProject
GITHUB_REPO=myorg/myproject
JIRA_PROJECT_KEY=PROJ

# GitHub credentials
GITHUB_APP_ID=123456
GITHUB_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----"

# Jira credentials
JIRA_URL=https://mycompany.atlassian.net
JIRA_EMAIL=dev@mycompany.com
JIRA_API_KEY=your_jira_token
```

**⚠️ Security**: Add `.env` to `.gitignore` to keep secrets safe!

## Create Agent Definition

Create `.github/agents/my-dev-helper.agent.md`:

```markdown
---
name: "my-dev-helper"
description: "Custom development assistant for ${PROJECT_NAME}"
model: "gpt-4o"
temperature: 0.7
max_tokens: 2000
tools:
  - github
  - jira
toolkit_configs:
  # Load Jira config from file
  - file: "configs/jira-config.json"
  
  # GitHub config inline with env vars
  - config:
      toolkit_name: "github"
      type: "github"
      settings:
        github_app_id: "${GITHUB_APP_ID}"
        github_app_private_key: "${GITHUB_PRIVATE_KEY}"
        github_repository: "${GITHUB_REPO}"
        selected_tools:
          - get_issue
          - list_pull_requests
          - create_pull_request_comment
---

# My Development Helper

You are a helpful assistant for the ${PROJECT_NAME} development team.

**Project**: ${PROJECT_NAME}  
**Repository**: ${GITHUB_REPO}  
**Jira Project**: ${JIRA_PROJECT_KEY}

## Your Responsibilities

- Help write and debug code
- Review pull requests
- Answer questions about our codebase
- Suggest improvements

## Project Context

- **Stack**: Python 3.10+, FastAPI, PostgreSQL
- **Coding Standards**: Follow PEP 8, use type hints
- **Testing**: Use pytest, aim for 80% coverage
- **Documentation**: Use Google-style docstrings

## Guidelines

1. Always provide working code examples
2. Reference our existing patterns
3. Suggest tests for new code
4. Keep responses concise but complete
```

## Create Toolkit Configs

### Jira Config with Environment Variables

Create `configs/jira-config.json`:

```json
{
  "toolkit_name": "jira",
  "type": "jira",
  "settings": {
    "base_url": "${JIRA_URL}",
    "cloud": true,
    "jira_configuration": {
      "username": "${JIRA_EMAIL}",
      "api_key": "${JIRA_API_KEY}"
    },
    "selected_tools": [
      "get_issue",
      "search_issues",
      "create_issue",
      "update_issue",
      "add_comment"
    ]
  }
}
```

**Note**: Environment variables in JSON files are automatically substituted at runtime, so your secrets stay in `.env` and never get committed to git!

**Note 2**: If you include toolkit configs in the agent's YAML frontmatter (see above), you don't need separate config files unless you want to reuse them across multiple agents.

## Usage Examples

### Interactive Development Session

**Option 1: Toolkits configured in agent file** (Recommended)

```bash
# Agent already has toolkit_configs in frontmatter
# This includes both Jira (from file) and GitHub (inline)
alita-cli agent chat .github/agents/my-dev-helper.agent.md
```

**Option 2: Add additional toolkits via command line**

```bash
# Add Confluence on top of agent's configured toolkits
alita-cli agent chat .github/agents/my-dev-helper.agent.md \
    --toolkit-config configs/confluence-config.json
```

**Option 3: Use only command-line toolkits** (without toolkit_configs in agent file)

```bash
# Explicit toolkit configs
alita-cli agent chat .github/agents/my-dev-helper.agent.md \
    --toolkit-config configs/jira-config.json \
    --toolkit-config configs/github-config.json
```

Example session:

```
🤖 Starting chat with local agent: my-dev-helper
Type your message and press Enter. Type 'exit' or 'quit' to end.

my-dev-helper> What issues are assigned to me in Jira?

[Agent uses Jira toolkit to search]
Found 5 issues assigned to you:
1. PROJ-123: Fix login bug (In Progress)
2. PROJ-124: Add pagination (To Do)
...

my-dev-helper> Show me the details of PROJ-123

[Agent gets issue details]
Issue: PROJ-123
Summary: Fix login bug
Status: In Progress
Description: Users report login failures when...

my-dev-helper> What PRs are open for this project?

[Agent uses GitHub toolkit]
Found 3 open pull requests:
1. #42: Fix authentication flow
2. #43: Add user preferences
...

my-dev-helper> Review PR #42

[Agent gets PR details and provides review]

my-dev-helper> /save
Save to file (default: conversation.json): dev-session-2025-11-27.json
Conversation saved to dev-session-2025-11-27.json

my-dev-helper> exit

Goodbye! 👋
```

### Automated Code Review

```bash
#!/bin/bash
# scripts/review-pr.sh

PR_NUMBER=$1

# Get PR diff
git fetch origin pull/$PR_NUMBER/head:pr-$PR_NUMBER
git checkout pr-$PR_NUMBER
DIFF=$(git diff main)

# Run agent review
alita-cli agent run .github/agents/my-dev-helper.agent.md \
    "Review this pull request and provide feedback:

PR #$PR_NUMBER

Changes:
$DIFF

Focus on:
- Code quality
- Test coverage
- Documentation
- Potential bugs
" \
    --toolkit-config configs/github-config.json \
    --output json \
    | jq -r '.response' > review-pr-$PR_NUMBER.md

echo "Review saved to review-pr-$PR_NUMBER.md"
```

### Daily Standup Report

```bash
#!/bin/bash
# scripts/standup-report.sh

TODAY=$(date +%Y-%m-%d)

# Generate standup report
alita-cli agent run .github/agents/my-dev-helper.agent.md \
    "Generate my standup report for today ($TODAY):

1. What did I complete yesterday?
2. What issues am I working on today?
3. Any blockers?

Check:
- Closed Jira issues in last 24 hours
- Open issues assigned to me
- Recent commits and PR activity
" \
    --toolkit-config configs/jira-config.json \
    --toolkit-config configs/github-config.json \
    --output json \
    | jq -r '.response' > standup-$TODAY.md

cat standup-$TODAY.md
```

### Create Issue from Error

```bash
#!/bin/bash
# scripts/report-bug.sh

ERROR_MESSAGE="$1"
STACK_TRACE="$2"

# Create Jira issue
alita-cli agent run .github/agents/my-dev-helper.agent.md \
    "A bug has occurred:

Error: $ERROR_MESSAGE

Stack trace:
$STACK_TRACE

Please:
1. Analyze the error
2. Create a Jira issue with:
   - Clear title
   - Description with error details
   - Suggested priority
   - Potential root cause
3. Return the issue key
" \
    --toolkit-config configs/jira-config.json \
    --output json \
    | jq -r '.response'
```

### Generate Release Notes

```bash
#!/bin/bash
# scripts/release-notes.sh

FROM_TAG=$1
TO_TAG=$2

# Get commits between tags
COMMITS=$(git log $FROM_TAG..$TO_TAG --pretty=format:"%h %s")

# Generate release notes
alita-cli agent run .github/agents/my-dev-helper.agent.md \
    "Generate release notes for version $TO_TAG:

Commits since $FROM_TAG:
$COMMITS

Please:
1. Group changes by category (Features, Fixes, Breaking Changes)
2. Link related Jira issues
3. Highlight important changes
4. Format in markdown
" \
    --toolkit-config configs/jira-config.json \
    --toolkit-config configs/github-config.json \
    > RELEASE_NOTES_$TO_TAG.md

echo "Release notes saved to RELEASE_NOTES_$TO_TAG.md"
```

## Integration with VS Code

### Create VS Code Task

Add to `.vscode/tasks.json`:

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Ask Dev Helper",
      "type": "shell",
      "command": "alita-cli",
      "args": [
        "agent",
        "run",
        ".github/agents/my-dev-helper.agent.md",
        "${input:question}",
        "--toolkit-config",
        "configs/jira-config.json"
      ],
      "problemMatcher": [],
      "presentation": {
        "reveal": "always",
        "panel": "new"
      }
    },
    {
      "label": "Chat with Dev Helper",
      "type": "shell",
      "command": "alita-cli",
      "args": [
        "agent",
        "chat",
        ".github/agents/my-dev-helper.agent.md",
        "--toolkit-config",
        "configs/jira-config.json",
        "--toolkit-config",
        "configs/github-config.json"
      ],
      "problemMatcher": [],
      "presentation": {
        "reveal": "always",
        "panel": "new"
      },
      "isBackground": true
    }
  ],
  "inputs": [
    {
      "id": "question",
      "type": "promptString",
      "description": "What do you want to ask?"
    }
  ]
}
```

Use: `Cmd+Shift+P` → `Tasks: Run Task` → `Chat with Dev Helper`

## Tips and Best Practices

### 1. Version Your Agents

```markdown
---
name: "my-dev-helper"
version: "1.2.0"
updated: "2025-11-27"
---
```

Track changes in git:

```bash
git log .github/agents/my-dev-helper.agent.md
```

### 2. Test Before Committing

```bash
# Test your agent
alita-cli agent chat .github/agents/my-dev-helper.agent.md

# Try various queries
my-dev-helper> What issues are in the backlog?
my-dev-helper> Review this code: [paste code]
my-dev-helper> Create a new feature issue

# Save successful session
my-dev-helper> /save test-session.json
```

### 3. Use Environment Variables

```bash
# Create environment-specific configs
export JIRA_URL="https://company.atlassian.net"
export JIRA_USER="dev@company.com"

envsubst < configs/jira-config.template.json > configs/jira-config.json

# Now use it
alita-cli agent chat .github/agents/my-dev-helper.agent.md \
    --toolkit-config configs/jira-config.json
```

### 4. Chain Multiple Agents

```bash
# Specialized agents for different tasks
alita-cli agent run .github/agents/analyzer.agent.md "Analyze requirements" > analysis.txt
alita-cli agent run .github/agents/designer.agent.md "Design based on: $(cat analysis.txt)" > design.txt
alita-cli agent run .github/agents/implementer.agent.md "Implement: $(cat design.txt)" > implementation.py
```

### 5. Save Conversation Context

```bash
# Start task, save thread
alita-cli agent run .github/agents/my-dev-helper.agent.md \
    "I need to implement user authentication" \
    --save-thread thread.json

# Continue later
THREAD_ID=$(jq -r '.thread_id' thread.json)
alita-cli agent run .github/agents/my-dev-helper.agent.md \
    "Now add password reset functionality" \
    --thread-id $THREAD_ID
```

## Troubleshooting

### Agent can't find toolkit

**Problem**: `Toolkit 'jira' not configured`

**Solution**: Make sure toolkit configs are passed:
```bash
alita-cli agent chat my-agent \
    --toolkit-config configs/jira-config.json
```

### Agent gives generic responses

**Problem**: Agent doesn't know project context

**Solution**: Improve agent definition with specific context:
```markdown
## Project Structure
- `src/` - Main application code
- `tests/` - Test files
- `docs/` - Documentation

## Key Files
- `src/auth.py` - Authentication logic
- `src/api.py` - API endpoints
```

### Local agent not working

**Problem**: `Agent definition not found`

**Solution**: Check file path and format:
```bash
# Verify file exists
ls -la .github/agents/my-agent.agent.md

# Show agent to verify format
alita-cli agent show .github/agents/my-agent.agent.md
```

## Next Steps

1. **Create your agent**: Copy and modify the example
2. **Set up toolkits**: Create configuration files
3. **Test interactively**: Use `agent chat` to refine
4. **Automate**: Create scripts for common workflows
5. **Share**: Commit agents to your repository

---

**See also**:
- `AGENT_CLI_GUIDE.md` - Complete agent documentation
- `CLI_GUIDE.md` - General CLI usage
- `.github/agents/sdk-dev.agent.md` - SDK development agent example
