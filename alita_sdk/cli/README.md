# Alita CLI User Guide

The Alita CLI is your command-line interface for building and running AI agents with powerful integrations.

## Table of Contents

- [Quick Start](#quick-start)
- [What Can You Do?](#what-can-you-do)
- [Working with Agents](#working-with-agents)
- [Using Toolkits](#using-toolkits)
- [MCP Server Integration](#mcp-server-integration)
- [Examples](#examples)
- [Developer Guide](#developer-guide)

## Quick Start

### Installation

```bash
pip install alita-sdk[cli]
```

### Configuration

Create a `.env` file in your project root:

```bash
ALITA_PROJECT_NAME=my-project
ALITA_DEPLOYMENT=https://domain.elitea.ai
ALITA_AUTH_TOKEN=your-token-here

# Optional: Custom directories
ALITA_DIR=.alita
```

### Your First Agent

Create `.alita/agents/hello.agent.md`:

```markdown
---
name: hello-assistant
description: A friendly greeting assistant
model: gpt-5
temperature: 0.1
---

You are a friendly assistant who greets users warmly.
```

Run it:

```bash
alita-cli agent chat .alita/agents/hello.agent.md
```

## What Can You Do?

### 🤖 **Work with AI Agents**
- Chat interactively with agents
- Run agents with single commands
- Use both cloud-hosted and local agents
- Give agents access to your filesystem

### 🔧 **Integrate External Tools**
- Connect to JIRA, GitHub, GitLab, Azure DevOps
- Configure tools with simple JSON/YAML files
- Agents can query issues, create tickets, search repos

### 🌐 **Browser Automation**
- Use Playwright MCP for web automation
- Navigate websites, click elements, take screenshots
- Browser state persists across actions

### 📁 **Filesystem Operations**
- Grant controlled filesystem access
- Read, write, search, and analyze files
- Security presets (full/safe/readonly)

## Working with Agents

### Agent Commands

#### List Available Agents

```bash
# List platform agents
alita-cli agent list

# List local agent files
alita-cli agent list --local
```

#### Show Agent Details

```bash
# Show platform agent
alita-cli agent show my-agent

# Show local agent
alita-cli agent show .alita/agents/my-agent.agent.md
```

#### Interactive Chat

```bash
# Interactive selection menu
alita-cli agent chat

# Chat with specific agent
alita-cli agent chat my-agent

# Chat with local agent
alita-cli agent chat .alita/agents/my-agent.agent.md

# Override settings
alita-cli agent chat my-agent --model gpt-4-turbo --temperature 0.5
```

**Chat Commands:**
- Type your message and press Enter
- `exit` or `quit` - Exit chat
- `/clear` - Clear conversation history
- `/history` - Show conversation
- `/save` - Save conversation to file
- `/help` - Show help

#### Single Command Execution

```bash
# Run agent with a message
alita-cli agent run my-agent "What is the weather today?"

# Get JSON output (for scripting)
alita-cli --output json agent run my-agent "Get status"
```

### Creating Local Agents

Local agents are defined in Markdown files with YAML frontmatter:

**File**: `.alita/agents/my-agent.agent.md`

```markdown
---
name: my-agent
description: What this agent does
model: gpt-4o
temperature: 0.7
max_tokens: 2000
tools:
  - jira
  - github
mcps:
  - server: playwright
    tools: [navigate, click, screenshot]
---

You are a helpful assistant who...
[Your system prompt and instructions here]
```

**Configuration Options:**

- `name` - Agent identifier
- `description` - What the agent does
- `model` - LLM model to use (gpt-4o, gpt-4-turbo, claude-3-sonnet, etc.)
- `temperature` - Creativity level (0.0 = focused, 1.0 = creative)
- `max_tokens` - Maximum response length
- `tools` - List of toolkit names to use
- `mcps` - MCP servers and tools to enable

### Filesystem Access

Give agents controlled access to your filesystem:

```bash
# Grant access to a directory
alita-cli agent chat code-agent --dir ./my-project

# The agent can now read/write files in ./my-project
```

**Security Presets:**

Configure in your agent definition:

```yaml
filesystem_tools_preset: safe  # full, safe, or readonly
```

- `readonly` - Can only read files and list directories
- `safe` - Can read, write, and create (no delete)
- `full` - Full access including delete operations

**Custom Tool Selection:**

```yaml
filesystem_tools_include: [read_file, write_file, list_directory]
filesystem_tools_exclude: [delete_file]
```

## Using Toolkits

Toolkits connect your agents to external services like JIRA, GitHub, GitLab, and Azure DevOps.

### Available Toolkits

```bash
# List available toolkits
alita-cli toolkit list

# Show toolkit details
alita-cli toolkit show jira

# Generate configuration template
alita-cli toolkit config jira > .alita/tools/jira.json
```

### Configuring Toolkits

Create a configuration file in JSON or YAML format:

**JSON Format** (`.alita/tools/jira.json`):
```json
{
  "toolkit_type": "jira",
  "toolkit_name": "jira",
  "credentials": {
    "JIRA_URL": "https://company.atlassian.net",
    "JIRA_USER": "user@example.com",
    "JIRA_TOKEN": "your-token"
  },
  "config": {
    "projects": ["PROJ"]
  }
}
```

**YAML Format** (`.alita/tools/github.yaml`):
```yaml
toolkit_type: github
toolkit_name: github
credentials:
  GITHUB_TOKEN: your-token
config:
  repositories:
    - owner/repo
```

### Using Toolkits with Agents

**1. Add to agent definition:**

```yaml
---
name: jira-agent
tools:
  - jira
  - github
---
```

**2. Provide config file when running:**

```bash
alita-cli agent chat jira-agent \
  --toolkit-config .alita/tools/jira.json \
  --toolkit-config .alita/tools/github.json
```

The agent can now query issues, create tickets, search repositories, and more!

## MCP Server Integration

### What is MCP?

MCP (Model Context Protocol) enables agents to use stateful external tools that maintain context between calls. Perfect for browser automation, database connections, and more.

**Popular MCP Servers:**
- **Playwright** - Browser automation
- **Filesystem** - Advanced file operations
- **Database** - SQL queries
- **Custom** - Build your own!

### Setting Up MCP Servers

**1. Create MCP configuration** (`.alita/mcp.json`):

```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["@playwright/mcp@latest"],
      "disabled": false
    }
  }
}
```

**2. Create agent with MCP tools** (`.alita/agents/browser-agent.agent.md`):

```markdown
---
name: browser-agent
description: Web automation assistant
model: gpt-4o
mcps:
  - server: playwright
    tools: [navigate, click, screenshot, snapshot]
---

You are a browser automation assistant. Use Playwright tools to:
- Navigate to websites
- Click on elements
- Take screenshots
- Analyze page content

The browser maintains state across all your actions.
```

**3. Use the agent:**

```bash
alita-cli agent chat browser-agent
> Navigate to example.com
> Click the "More information" link
> What's the current page title?
```

The browser stays open and maintains state throughout the entire conversation!

### Available MCP Servers

**Playwright** - Browser automation
```bash
npx @playwright/mcp@latest
```
Tools: `navigate`, `click`, `screenshot`, `snapshot`, `fill_form`, `evaluate`

**Filesystem** - Advanced file operations
```bash
npx @modelcontextprotocol/server-filesystem /path/to/allowed/dir
```
Tools: Enhanced file operations with advanced search and analysis

**Custom Servers** - Build your own MCP server for any stateful tool!

### Why Sessions Matter

MCP servers need persistent sessions because they maintain state:

- **Browser automation**: Keep tabs and navigation history
- **Database connections**: Maintain transactions and connection pools
- **File systems**: Track current directory and open files

The CLI automatically manages these sessions for you. Just define your MCP servers in `mcp.json` and add them to your agent!

## Examples

### Example 1: Code Analysis Agent

**Agent**: `.alita/agents/code-reviewer.agent.md`

```markdown
---
name: code-reviewer
description: Analyzes code for issues and improvements
model: gpt-4o
temperature: 0.3
filesystem_tools_preset: readonly
---

You are an expert code reviewer. Analyze code for:
- Potential bugs and security issues
- Performance improvements
- Best practices and code quality
- Documentation suggestions
```

**Usage**:
```bash
alita-cli agent chat code-reviewer --dir ./my-project
> Analyze the files in src/utils/ and suggest improvements
```

### Example 2: JIRA Assistant

**Toolkit Config**: `.alita/tools/jira.json`

```json
{
  "toolkit_type": "jira",
  "toolkit_name": "jira",
  "credentials": {
    "JIRA_URL": "https://company.atlassian.net",
    "JIRA_USER": "your@email.com",
    "JIRA_TOKEN": "your-token"
  },
  "config": {
    "projects": ["PROJ", "TASK"]
  }
}
```

**Agent**: `.alita/agents/jira-assistant.agent.md`

```markdown
---
name: jira-assistant
description: Manages JIRA tickets
model: gpt-4o
tools:
  - jira
---

You help manage JIRA tickets. You can:
- Search for tickets
- Create new issues
- Update ticket status
- Add comments
```

**Usage**:
```bash
# Interactive
alita-cli agent chat jira-assistant --toolkit-config .alita/tools/jira.json
> What are the open bugs in PROJ?
> Create a new task for fixing the login issue

# Single command
alita-cli agent run jira-assistant "List all high-priority tickets" \
  --toolkit-config .alita/tools/jira.json
```

### Example 3: Web Research Agent

**MCP Config**: `.alita/mcp.json`

```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["@playwright/mcp@latest"]
    }
  }
}
```

**Agent**: `.alita/agents/researcher.agent.md`

```markdown
---
name: researcher
description: Researches topics on the web
model: gpt-4o
mcps:
  - server: playwright
    tools: [navigate, click, screenshot, snapshot]
---

You are a research assistant. Use the browser to:
1. Navigate to relevant websites
2. Extract key information
3. Follow links to gather comprehensive data
4. Take screenshots of important findings
```

**Usage**:
```bash
alita-cli agent chat researcher
> Research the latest trends in AI agents and summarize your findings
> Navigate to arxiv.org and find recent papers on LLMs
> Take a screenshot of the most cited paper
```

### Example 4: Documentation Generator

**Agent**: `.alita/agents/doc-generator.agent.md`

```markdown
---
name: doc-generator
description: Generates documentation from code
model: gpt-4o
temperature: 0.5
filesystem_tools_preset: safe
---

You generate documentation from code. For each file:
1. Read and understand the code
2. Create clear documentation
3. Write it to a docs/ directory
4. Include examples and usage
```

**Usage**:
```bash
alita-cli agent run doc-generator \
  "Generate documentation for all Python files in src/" \
  --dir ./my-project
```

## Common Use Cases

### 🎯 Task Automation
Create agents that automate repetitive tasks:
- Generate reports from JIRA tickets
- Update documentation automatically
- Process and organize files
- Monitor and analyze logs

### 🔍 Research & Analysis
Build agents that gather and analyze information:
- Web research with browser automation
- Code analysis and review
- Data extraction and summarization
- Competitive analysis

### 🤝 Integration Hub
Connect multiple services through a single agent:
- Sync JIRA tickets with GitHub issues
- Update documentation from code changes
- Aggregate data from multiple sources
- Cross-platform notifications

### 🛠️ Development Assistant
Enhance your development workflow:
- Code review and suggestions
- Test generation
- Refactoring assistance
- Documentation generation

## Troubleshooting

### "Failed to connect to MCP server"

**Solution:**
1. Check `mcp.json` syntax is valid
2. Test the command manually: `npx @playwright/mcp@latest`
3. Ensure `"disabled": false` in the server config
4. Check you have Node.js and npm installed

### "Tool not found" Error

**Solution:**
1. Verify toolkit is listed in agent's `tools` section
2. Check toolkit config file path is correct
3. Use `--toolkit-config` flag if needed
4. Verify credentials in config file are valid

### "Path outside allowed directory"

**Solution:**
1. Use `--dir` flag to specify the allowed directory
2. Ensure paths in commands stay within that directory
3. Check for symbolic links or `..` in paths

### Browser Returns to Blank Page

**Solution:**
This shouldn't happen - the CLI automatically manages MCP sessions. If it does:
1. Restart your terminal
2. Check you're using the latest version: `pip install --upgrade alita-sdk`
3. Try recreating your MCP config file

### Agent Response is Too Long/Short

**Solution:**
Adjust `max_tokens` in your agent definition:
```yaml
max_tokens: 4000  # Increase for longer responses
```

Or override at runtime:
```bash
alita-cli agent chat my-agent --max-tokens 4000
```

## Developer Guide

### Project Structure

```
cli/
├── agents.py           # Agent commands (chat, run, list, show)
├── agent_executor.py   # Agent setup and execution
├── agent_loader.py     # Load agent definitions from markdown
├── agent_ui.py         # Terminal UI components
├── toolkit.py          # Toolkit commands
├── toolkit_loader.py   # Load toolkit configs
├── mcp_loader.py       # MCP server management
├── cli.py              # Main CLI entry point
├── config.py           # Configuration (.env handling)
└── tools/
    └── filesystem.py   # Filesystem tools
```

### Adding a New Toolkit

1. **Implement toolkit** in `alita_sdk/toolkits/`:
```python
class MyToolkit:
    def __init__(self, credentials, config):
        self.api_key = credentials['API_KEY']
    
    def get_tools(self):
        return [tool1, tool2, tool3]
```

2. **Register in** `toolkit_loader.py`
3. **Create config template**
4. **Test with an agent**

### Adding New MCP Servers

No code changes needed! Just:
1. Add server to `.alita/mcp.json`
2. Use in agent definition
3. Test the integration

### Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/

# Test specific agent
alita-cli agent run test-agent "Hello" --debug
```

### Contributing

Contributions are welcome! Please:
- Follow existing code patterns
- Add tests for new features
- Update documentation
- Submit pull requests to the main repository

## Learn More

### External Resources
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [LangChain MCP Adapters](https://github.com/langchain-ai/langchain-mcp-adapters)
- [Click Framework](https://click.palletsprojects.com/)
- [Rich Terminal](https://rich.readthedocs.io/)

## Support

- **Issues**: [GitHub Issues](https://github.com/ProjectAlita/projectalita.github.io/issues)

---

**Happy Agent Building! 🚀**
