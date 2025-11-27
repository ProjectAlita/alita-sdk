# Agent CLI Enhancements - Quick Reference

## New Features

### 1. Configurable Agents Directory
```bash
# In .env
AGENTS_DIR=.github/agents

# Or override with flag
alita-cli agent list --local --directory custom/path
```

### 2. Environment Variables in Configs

**In .env:**
```bash
JIRA_URL=https://company.atlassian.net
JIRA_EMAIL=dev@company.com
JIRA_API_KEY=your_token
GITHUB_REPO=myorg/myproject
PROJECT_NAME=MyProject
```

**In agent file:**
```markdown
---
name: "my-agent"
---

Working on ${PROJECT_NAME}
Repository: ${GITHUB_REPO}
```

**In toolkit config:**
```json
{
  "toolkit_name": "jira",
  "settings": {
    "base_url": "${JIRA_URL}",
    "jira_configuration": {
      "username": "${JIRA_EMAIL}",
      "api_key": "${JIRA_API_KEY}"
    }
  }
}
```

### 3. Inline Toolkit Configs

```markdown
---
name: "my-agent"
tools:
  - jira
  - github
toolkit_configs:
  # From file
  - file: "configs/jira-config.json"
  
  # Inline config
  - config:
      toolkit_name: "github"
      type: "github"
      settings:
        github_app_id: "${GITHUB_APP_ID}"
        github_repository: "${GITHUB_REPO}"
---

# Agent prompt...
```

### 4. Auto-Add Toolkits

```bash
# Agent has tools: [jira]
# Add GitHub config
alita-cli agent chat my-agent --toolkit-config github-config.json

# Result: tools automatically becomes [jira, github]
```

## Migration Guide

### Before (hardcoded):
```json
{
  "settings": {
    "api_key": "hardcoded_secret_here"
  }
}
```

### After (with env vars):
```json
{
  "settings": {
    "api_key": "${API_KEY}"
  }
}
```

```bash
# .env (gitignored)
API_KEY=hardcoded_secret_here
```

## Security Best Practices

1. **Add .env to .gitignore**
   ```bash
   echo ".env" >> .gitignore
   ```

2. **Use env vars for all secrets**
   - API keys
   - Tokens
   - Private keys
   - Passwords

3. **Commit config files safely**
   - Toolkit configs with `${VAR}` syntax ✅
   - Agent definitions with `${VAR}` syntax ✅
   - Never commit `.env` ❌

4. **Team workflow**
   ```bash
   # Share template
   cp .env .env.example
   # Remove sensitive values from .env.example
   git add .env.example
   
   # Each team member creates their own .env
   cp .env.example .env
   # Fill in their own credentials
   ```

## Examples

### Complete Setup

**Step 1: Create .env**
```bash
cat > .env <<'EOF'
# Platform
DEPLOYMENT_URL=https://your.alita.ai
PROJECT_ID=123
API_KEY=your_key

# Agents
AGENTS_DIR=.github/agents

# Project
PROJECT_NAME=MyProject
GITHUB_REPO=org/repo

# Credentials
JIRA_URL=https://company.atlassian.net
JIRA_EMAIL=dev@company.com
JIRA_API_KEY=token
EOF
```

**Step 2: Create agent**
```bash
cat > .github/agents/dev.agent.md <<'EOF'
---
name: "dev-helper"
description: "Helper for ${PROJECT_NAME}"
tools:
  - jira
toolkit_configs:
  - file: "configs/jira.json"
---

# Development Helper for ${PROJECT_NAME}
EOF
```

**Step 3: Create toolkit config**
```bash
mkdir -p configs
cat > configs/jira.json <<'EOF'
{
  "toolkit_name": "jira",
  "type": "jira",
  "settings": {
    "base_url": "${JIRA_URL}",
    "jira_configuration": {
      "username": "${JIRA_EMAIL}",
      "api_key": "${JIRA_API_KEY}"
    }
  }
}
EOF
```

**Step 4: Use it**
```bash
# List agents (uses AGENTS_DIR from .env)
alita-cli agent list --local

# Show agent (env vars substituted)
alita-cli agent show .github/agents/dev.agent.md

# Chat (toolkit auto-loaded from agent)
alita-cli agent chat .github/agents/dev.agent.md
```

## Testing

Run the test suite:
```bash
./test-agent-enhancements.sh
```

## Documentation

- **Complete Guide**: `alita-sdk/docs/cli/AGENT_CLI_GUIDE.md`
- **Example Workflow**: `alita-sdk/docs/cli/custom-agent-example.md`
- **Full Summary**: `AGENT_CLI_ENHANCEMENTS.md`
- **Example Files**:
  - `alita-sdk/examples/agent-with-env-vars.agent.md`
  - `alita-sdk/examples/env-example.env`
  - `alita-sdk/examples/jira-config-with-env.json`

## Troubleshooting

**Env vars not substituted:**
```bash
# Check .env is loaded
alita-cli config

# Verify variable is set
echo $MY_VAR

# Use --debug to see what's happening
alita-cli --debug agent show my-agent.agent.md
```

**Agent not found:**
```bash
# Check AGENTS_DIR
alita-cli config

# List agents
alita-cli agent list --local

# Use explicit path
alita-cli agent show path/to/agent.agent.md
```

**Toolkit not working:**
```bash
# Verify config is loaded
alita-cli --debug agent chat my-agent

# Check toolkit auto-added
alita-cli agent show my-agent  # Check Tools list
```

---

**All features are backward compatible!** Old agents still work without changes.
