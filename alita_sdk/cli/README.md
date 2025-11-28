# Alita CLI User Guide

The Alita CLI is your command-line interface for building and running AI agents with powerful integrations.

## Table of Contents

- [Quick Start](#quick-start)
- [What Can You Do?](#what-can-you-do)
- [Working with Agents](#working-with-agents)
- [Interactive Chat Commands](#interactive-chat-commands)
- [Session Management](#session-management)
- [Approval Modes](#approval-modes)
- [Planning Tools](#planning-tools)
- [Terminal Execution](#terminal-execution)
- [Using Toolkits](#using-toolkits)
- [MCP Server Integration](#mcp-server-integration)
- [Examples](#examples)
- [Common Use Cases](#common-use-cases)
- [Troubleshooting](#troubleshooting)
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
ALITA_DIR=~/.alita
```

### Your First Agent

Create `.alita/agents/hello.agent.md`:

```markdown
---
name: hello-assistant
description: A friendly greeting assistant
model: gpt-4o
temperature: 0.1
---

You are a friendly assistant who greets users warmly.
```

Run it:

```bash
alita agent chat .alita/agents/hello.agent.md
```

## What Can You Do?

### 🤖 **Work with AI Agents**
- Chat interactively with agents
- Run agents with single commands
- Use both cloud-hosted and local agents
- Give agents access to your filesystem
- **Switch agents mid-conversation** with `/agent`
- **Switch models on the fly** with `/model`

### 🔧 **Integrate External Tools**
- Connect to JIRA, GitHub, GitLab, Azure DevOps
- Configure tools with simple JSON/YAML files
- Agents can query issues, create tickets, search repos
- **Add toolkits dynamically** with `/add_toolkit`

### 🌐 **Browser & MCP Automation**
- Use Playwright MCP for web automation
- Navigate websites, click elements, take screenshots
- Browser state persists across actions
- **Add MCP servers on the fly** with `/add_mcp`

### 📁 **Filesystem Operations**
- Grant controlled filesystem access
- Read, write, search, and analyze files
- Security presets (full/safe/readonly)
- **Mount directories dynamically** with `/dir`

### 💻 **Terminal Execution**
- Execute shell commands from agents
- Sandboxed to mounted directory only
- Configurable blocked command patterns
- Security controls prevent dangerous operations

### 📋 **Planning & Task Management**
- Create structured execution plans
- Track step-by-step progress
- Persistent plans saved to sessions
- Visual progress with checkboxes

### 💾 **Session Persistence**
- Automatic session management
- Resume previous conversations
- Memory + plan state preserved
- List and switch between sessions

## Working with Agents

### Agent Commands

#### List Available Agents

```bash
# List platform agents
alita agent list

# List local agent files
alita agent list --local
```

#### Show Agent Details

```bash
# Show platform agent
alita agent show my-agent

# Show local agent
alita agent show .alita/agents/my-agent.agent.md
```

#### Interactive Chat

```bash
# Interactive selection menu
alita agent chat

# Chat with specific agent
alita agent chat my-agent

# Chat with local agent
alita agent chat .alita/agents/my-agent.agent.md

# Override settings
alita agent chat my-agent --model gpt-4-turbo --temperature 0.5

# Mount a directory for filesystem/terminal access
alita agent chat my-agent --dir ./my-project
```

#### Single Command Execution

```bash
# Run agent with a message
alita agent run my-agent "What is the weather today?"

# Get JSON output (for scripting)
alita --output json agent run my-agent "Get status"
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

## Interactive Chat Commands

When chatting with an agent, you have access to powerful slash commands:

### Basic Commands

| Command | Description |
|---------|-------------|
| `/help` | Show all available commands |
| `/clear` | Clear conversation history |
| `/history` | Display conversation history |
| `/save [filename]` | Save conversation to file |
| `exit` or `quit` | Exit the chat |

### Configuration Commands

| Command | Description |
|---------|-------------|
| `/model` | Switch LLM model (interactive selection) |
| `/agent` | Switch to a different agent |
| `/reload` | Reload agent definition from file (hot reload) |
| `/mode [always\|auto\|yolo]` | Set approval mode for tool execution |
| `/verbose [on\|off]` | Toggle verbose output |

### Dynamic Tool Commands

| Command | Description |
|---------|-------------|
| `/dir <path>` | Mount a directory for filesystem/terminal access |
| `/add_mcp` | Add an MCP server from your configuration |
| `/add_toolkit` | Add a toolkit dynamically |

### Session Commands

| Command | Description |
|---------|-------------|
| `/session` or `/session list` | List all saved sessions |
| `/session resume <id>` | Resume a previous session |
| `/plan` | Show current plan status |

### Example Session

```
You: /model
[Interactive model selection appears]
✓ Model switched to claude-sonnet-4

You: /dir ./my-project
✓ Mounted: /Users/me/my-project
  Terminal + filesystem tools enabled.

You: /add_mcp
[Interactive MCP selection appears]
✓ Added MCP: playwright

You: /mode auto
✓ Mode set to: auto (auto-approve tool calls)

You: Analyze the codebase and create a plan
[Agent creates plan and executes tools automatically]

# After editing your agent file externally...
You: /reload
✓ Reloaded agent: my-agent
  System prompt updated (2456 chars)
```

## Session Management

Sessions automatically persist your conversation memory and plans, allowing you to resume work later.

### How Sessions Work

When you start a chat, a session is automatically created with a unique ID like `20251128-143522-a1b2c3`. All conversation memory and plans are saved to:

```
~/.alita/sessions/<session_id>/
├── memory.db      # SQLite checkpoint for conversation memory
├── plan.json      # Plan state with steps and progress
└── metadata.json  # Agent name, model, timestamps
```

### Listing Sessions

```
You: /session

📋 Saved Sessions:

  ○ 20251128-143522-a1b2 - Fix authentication bug [2/5]
      Testing Agent (claude-sonnet-4) • 2025-11-28 14:35 ◀ current
  ● 20251128-120000-c3d4
      Alita (gpt-4o) • 2025-11-28 12:00
  ✓ 20251127-090000-e5f6 - Setup CI/CD pipeline [5/5]
      DevOps Agent (gpt-4o) • 2025-11-27 09:00

Usage: /session resume <session_id>
```

**Status Icons:**
- `○` - Has plan in progress
- `●` - Session without plan
- `✓` - Plan completed

### Resuming Sessions

```
You: /session resume 20251128-143522-a1b2

╭─ Session Resumed ─────────────────────────────────────────╮
│ ✓ Resumed session: 20251128-143522-a1b2                   │
│ Agent: Testing Agent • Model: claude-sonnet-4             │
│                                                           │
│ 📋 Fix authentication bug                                 │
│    ☑ 1. Analyze current auth flow (completed)             │
│    ☑ 2. Identify security issues (completed)              │
│    ☐ 3. Implement token refresh                           │
│    ☐ 4. Add unit tests                                    │
│    ☐ 5. Update documentation                              │
╰───────────────────────────────────────────────────────────╯
```

Your conversation history and plan are restored - continue right where you left off!

## Approval Modes

Control how the agent executes tools with approval modes:

### Available Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| `always` | Prompt before each tool execution | Default - safe for learning |
| `auto` | Auto-approve, but show tool calls | Trusted workflows |
| `yolo` | No confirmations, minimal output | Automated scripts |

### Setting the Mode

**At startup:**
```bash
alita agent chat my-agent --mode auto
```

**During chat:**
```
You: /mode auto
✓ Mode set to: auto (auto-approve tool calls)

You: /mode
🔧 Approval Mode:

  ○ always  - Confirm before each tool execution
  ● auto    - Execute tools without confirmation
  ○ yolo    - No confirmations, skip safety warnings
```

### Approval Prompts (always mode)

When a tool is about to execute, you'll see:

```
╭─ Tool: run_terminal_command ──────────────────────────────╮
│ Command: npm install                                      │
│ Working Directory: /Users/me/my-project                   │
╰───────────────────────────────────────────────────────────╯
Execute this tool? [Y/n/always/never]:
```

**Options:**
- `Y` or Enter - Execute this tool
- `n` - Skip this tool
- `always` - Switch to auto mode for the rest of the session
- `never` - Deny all future tool calls

## Planning Tools

Agents can create and manage structured execution plans for complex tasks.

### How Plans Work

When working on multi-step tasks, the agent can create a plan:

```
You: Refactor the authentication module

╭─ Plan Created ────────────────────────────────────────────╮
│ 📋 Refactor Authentication Module                         │
│    ☐ 1. Analyze current auth implementation               │
│    ☐ 2. Identify code smells and issues                   │
│    ☐ 3. Create new auth service class                     │
│    ☐ 4. Migrate existing code to new structure            │
│    ☐ 5. Update all imports and references                 │
│    ☐ 6. Add comprehensive tests                           │
│    ☐ 7. Update documentation                              │
╰───────────────────────────────────────────────────────────╯
```

As steps complete, they're automatically marked:

```
╭─ Plan Updated ────────────────────────────────────────────╮
│ 📋 Refactor Authentication Module                         │
│    ☑ 1. Analyze current auth implementation (completed)   │
│    ☑ 2. Identify code smells and issues (completed)       │
│    ☐ 3. Create new auth service class                     │
│    ...                                                    │
╰───────────────────────────────────────────────────────────╯
```

### Viewing the Plan

```
You: /plan

📋 Refactor Authentication Module [3/7]

   ☑ 1. Analyze current auth implementation (completed)
   ☑ 2. Identify code smells and issues (completed)
   ☑ 3. Create new auth service class (completed)
   ☐ 4. Migrate existing code to new structure
   ☐ 5. Update all imports and references
   ☐ 6. Add comprehensive tests
   ☐ 7. Update documentation
```

### Plan Persistence

Plans are automatically saved to your session directory and persist across restarts. Resume a session to continue where you left off.

## Terminal Execution

When a directory is mounted, agents can execute shell commands in a sandboxed environment.

### Enabling Terminal Access

```bash
# Mount at startup
alita agent chat my-agent --dir ./my-project

# Or mount during chat
You: /dir ./my-project
✓ Mounted: /Users/me/my-project
  Terminal + filesystem tools enabled.
```

### Security Features

Terminal execution includes multiple safety layers:

**1. Directory Sandboxing**
- Commands only execute within the mounted directory
- Path traversal attempts are blocked
- Working directory is always the mounted path

**2. Blocked Command Patterns**

By default, dangerous commands are blocked:

```
rm -rf /           # Destructive root operations
sudo *             # Privilege escalation
chmod 777          # Unsafe permissions
> /dev/*           # Device manipulation
:(){ :|:& };:      # Fork bombs
...and more
```

**3. Custom Blocked Patterns**

Create `~/.alita/blocked_patterns.txt` to add your own:

```
# Custom blocked patterns
*password*
*secret*
curl * | bash
```

### Terminal Tool Usage

The agent can run commands like:

```
You: Run the test suite

╭─ Tool: run_terminal_command ──────────────────────────────╮
│ Command: npm test                                         │
│ Working Directory: /Users/me/my-project                   │
╰───────────────────────────────────────────────────────────╯
Execute this tool? [Y/n]:

Running: npm test

PASS  src/auth.test.js
PASS  src/utils.test.js

Test Suites: 2 passed, 2 total
Tests:       12 passed, 12 total
```

## Using Toolkits

Toolkits connect your agents to external services like JIRA, GitHub, GitLab, and Azure DevOps.

### Available Toolkits

```bash
# List available toolkits
alita toolkit list

# Show toolkit details
alita toolkit show jira

# Generate configuration template
alita toolkit config jira > .alita/tools/jira.json
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
alita agent chat jira-agent \
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
alita agent chat browser-agent
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
alita agent chat code-reviewer --dir ./my-project
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
alita agent chat jira-assistant --toolkit-config .alita/tools/jira.json
> What are the open bugs in PROJ?
> Create a new task for fixing the login issue

# Single command
alita agent run jira-assistant "List all high-priority tickets" \
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
alita agent chat researcher
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
alita agent run doc-generator \
  "Generate documentation for all Python files in src/" \
  --dir ./my-project
```

### Example 5: Testing Agent with Planning

**Agent**: `.alita/agents/testing-agent.agent.md`

```markdown
---
name: testing-agent
description: Creates comprehensive test suites
model: claude-sonnet-4
temperature: 0.3
filesystem_tools_preset: safe
---

You are a testing expert. When given a codebase:
1. Create a plan with clear steps
2. Analyze existing code coverage
3. Identify untested functions
4. Generate test files
5. Run tests and verify they pass
6. Update the plan as you complete each step

Always use update_plan to track your progress.
```

**Usage**:
```bash
alita agent chat testing-agent --dir ./my-project --mode auto
> Create a comprehensive test suite for the auth module
```

The agent will create a plan, execute each step, and track progress automatically.

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
alita agent chat my-agent --max-tokens 4000
```

### "Command blocked by security policy"

**Solution:**
The command matches a blocked pattern. Check `~/.alita/blocked_patterns.txt`:
1. Review the blocked patterns
2. Remove or modify patterns if they're too restrictive
3. If legitimate, rephrase the command

### "No directory mounted" for terminal commands

**Solution:**
Terminal commands require a mounted directory:
```bash
# At startup
alita agent chat my-agent --dir ./my-project

# Or during chat
You: /dir ./my-project
```

### "Step limit reached" Error

**What it means:**
The agent has exceeded the maximum number of execution steps (default: 25). This happens with complex tasks requiring many tool calls.

**In interactive chat mode:**
When this happens, you'll be prompted with options:
```
⚠ Step limit reached (25 steps)

What would you like to do?
  c - Continue execution (agent will resume from checkpoint)
  s - Stop and get partial results
  n - Start a new request
```

Choose `c` to continue from where the agent left off - the checkpoint preserves all state.

**In single-run mode (`alita agent run`):**
The command will stop with suggestions:
- Use `alita agent chat` for interactive continuation
- Break the task into smaller, focused requests
- Check if partial work was completed (files created, etc.)

**Prevention:**
- Break complex tasks into smaller steps
- Use the planning tools to track progress across multiple interactions
- For very complex tasks, use multiple focused requests instead of one large one
You: /dir ./my-project
```

### Session not resuming properly

**Solution:**
1. Check session exists: `/session list`
2. Use the full session ID: `/session resume 20251128-143522-a1b2`
3. Session files are in `~/.alita/sessions/`

## Developer Guide

### Project Structure

```
cli/
├── cli.py              # Main CLI entry point
├── config.py           # Configuration (.env handling)
├── agents.py           # Agent commands (chat, run, list, show)
├── agent_executor.py   # Agent setup and execution
├── agent_loader.py     # Load agent definitions from markdown
├── agent_ui.py         # Terminal UI components (banners, panels)
├── input_handler.py    # Readline input with tab completion
├── toolkit.py          # Toolkit commands
├── toolkit_loader.py   # Load toolkit configs
├── mcp_loader.py       # MCP server management
└── tools/
    ├── __init__.py     # Tool exports
    ├── filesystem.py   # Filesystem tools (read, write, search)
    ├── terminal.py     # Terminal execution (sandboxed)
    ├── planning.py     # Planning tools + session management
    └── approval.py     # Approval mode wrapper
```

### Session Storage

Sessions are stored at `~/.alita/sessions/<session_id>/`:

```
sessions/
└── 20251128-143522-a1b2/
    ├── memory.db       # SQLite checkpoint (LangGraph)
    ├── plan.json       # Plan state
    └── metadata.json   # Agent info, timestamps
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
alita agent run test-agent "Hello" --verbose debug
```

### Key Concepts

**Approval Wrapper**: Tools are wrapped with `ApprovalToolWrapper` which:
- Intercepts tool calls before execution
- Prompts user based on approval mode
- Logs tool usage for debugging

**Session Memory**: Uses LangGraph's `SqliteSaver` for:
- Persisting conversation checkpoints
- Resuming sessions across restarts
- Storing agent state

**Plan State**: Managed by `PlanState` class:
- Steps with completion tracking
- JSON serialization to session directory
- Visual rendering with checkboxes

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
