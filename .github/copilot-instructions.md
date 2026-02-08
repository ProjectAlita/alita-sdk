# Alita SDK - AI Agent Instructions

## Project Overview

**Alita SDK** is a LangChain-based framework for building intelligent AI agents that integrate with the Alita Platform. The SDK provides:
- 60+ pre-built toolkits (JIRA, GitHub, GitLab, Azure DevOps, Confluence, Slack, etc.)
- Interactive CLI for agent chat with dynamic tool/model switching
- LangGraph-based agent orchestration (React agents & pipelines)
- Filesystem tools with security presets, MCP server support, terminal execution
- Vector store integration for code/document indexing and semantic search

## Project Structure

```
alita-sdk/
├── alita_sdk/                    # Core SDK package
│   ├── runtime/                  # Agent execution runtime
│   │   ├── langchain/           # LangGraph agent implementations
│   │   │   ├── assistant.py     # Main Assistant class (agent factory)
│   │   │   ├── langraph_agent.py # Graph builder (create_graph)
│   │   │   └── constants.py     # System prompts & personas
│   │   ├── clients/             # Platform API clients
│   │   │   └── client.py        # AlitaClient (LLM management)
│   │   ├── middleware/          # Agent middleware system
│   │   ├── toolkits/            # Legacy toolkit loading
│   │   └── utils/               # Utilities (MCP OAuth, etc.)
│   │
│   ├── tools/                    # 60+ toolkit implementations
│   │   ├── elitea_base.py       # Base classes for toolkits
│   │   ├── github/              # GitHub toolkit
│   │   ├── jira/                # JIRA toolkit
│   │   ├── gitlab/              # GitLab toolkit
│   │   ├── ado/                 # Azure DevOps toolkit
│   │   ├── confluence/          # Confluence toolkit
│   │   ├── chunkers/            # Document chunking strategies
│   │   └── ...                  # 55+ more toolkit directories
│   │
│   ├── cli/                      # Interactive command-line interface
│   │   ├── cli.py               # Entry point (Click commands)
│   │   ├── agents.py            # Agent chat & execution logic
│   │   ├── agent_loader.py      # Load agent definitions (YAML+MD)
│   │   ├── toolkit_loader.py    # Load toolkit configs (JSON/YAML)
│   │   ├── mcp_loader.py        # MCP server management
│   │   └── tools/               # CLI-specific tools
│   │       ├── filesystem.py    # 15 filesystem tools (sandboxed)
│   │       ├── terminal.py      # Terminal execution (sandboxed)
│   │       └── planning.py      # Task planning tools
│   │
│   ├── configurations/           # Platform toolkit configurations
│   │   ├── github.py            # GitHub config schema
│   │   ├── jira.py              # JIRA config schema
│   │   └── ...                  # 40+ configuration modules
│   │
│   └── community/                # Community-contributed tools
│       └── inventory/           # Code graph inventory toolkit
│
├── .alita/                       # Local development workspace
│   ├── agents/                  # Agent definitions (*.agent.md)
│   ├── tools/                   # Toolkit configurations (*.json)
│   ├── mcp.json                 # MCP server configuration
│   └── tests/test_pipelines/   # Declarative test framework
│
├── tests/                        # Unit/integration tests
├── docs/                         # Documentation
├── scripts/                      # Utility scripts
└── pyproject.toml               # Build configuration
```

## Core Modules Breakdown

| Module | Purpose | Key Components | Entry Points |
|--------|---------|----------------|--------------|
| **alita_sdk/runtime/langchain/** | LangGraph agent orchestration | `Assistant` (agent factory), `create_graph()` (graph builder), `LangGraphAgentRunnable` | `Assistant.__init__()` creates agents from config |
| **alita_sdk/runtime/clients/** | Platform API & LLM management | `AlitaClient` (API wrapper), LLM instance management, model switching | `AlitaClient.application()` loads agent configs |
| **alita_sdk/tools/** | 60+ toolkit implementations | Each toolkit has `toolkit_config_schema()`, `get_toolkit()`, `get_tools()` | `get_tools()` in `__init__.py` registers all toolkits |
| **alita_sdk/tools/elitea_base.py** | Base classes for toolkits | `BaseToolApiWrapper`, `BaseVectorStoreToolApiWrapper`, `BaseCodeToolApiWrapper` | Extend these for new toolkits |
| **alita_sdk/cli/** | Interactive CLI commands | Agent chat, toolkit testing, MCP integration, dynamic model/tool switching | `alita-cli` command (Click app) |
| **alita_sdk/cli/tools/filesystem.py** | Sandboxed filesystem access | 15 tools (read, write, edit, search, tree, etc.), security presets (readonly/safe/full) | `get_filesystem_tools()` |
| **alita_sdk/cli/tools/terminal.py** | Sandboxed terminal execution | Command execution in mounted directory, blocked patterns, path validation | `get_terminal_tools()` |
| **alita_sdk/cli/agent_loader.py** | Agent definition loading | Parse Markdown + YAML frontmatter, Jinja2 variable resolution, UTF-8 fallback | `load_agent_definition()` |
| **alita_sdk/cli/toolkit_loader.py** | Toolkit config loading | Load JSON/YAML configs, env var substitution (`${VAR}`), validation | `load_toolkit_config()` |
| **alita_sdk/cli/mcp_loader.py** | MCP server management | Load mcp.json, start/stop servers, OAuth token refresh, session persistence | `MCPSessionManager` |
| **alita_sdk/configurations/** | Platform toolkit schemas | Pydantic schemas for each toolkit's configuration, credential management | Used by platform UI for config forms |
| **alita_sdk/runtime/middleware/** | Agent middleware system | Pre/post-processing hooks, custom tool injection, prompt augmentation | `Middleware` base class, `MiddlewareManager` |
| **alita_sdk/tools/chunkers/** | Document chunking | Markdown, code, JSON, universal chunkers for vector store indexing | `universal_chunker()` auto-detects file type |
| **alita_sdk/community/inventory/** | Code graph analysis | Entity extraction, relationship mapping, impact analysis, graph search | `InventoryToolkit` for codebase understanding |

## Agent Definition Format (Markdown with YAML frontmatter)
```markdown
---
name: agent-name
model: gpt-4o
temperature: 0.7
tools: []  # Platform tools
toolkit_configs: []  # Toolkit references
filesystem_tools_preset: safe  # full|safe|readonly
mcps: []  # MCP server names
---
System prompt goes here
```
Stored in `.alita/agents/*.agent.md`, loaded by [agent_loader.py](../alita_sdk/cli/agent_loader.py)

## Development Workflows

### Running the CLI
```bash
# Interactive chat with agent
alita-cli agent chat .alita/agents/my-agent.agent.md

# Mount directory for filesystem access
alita-cli agent chat my-agent --dir ./project

# Dynamic switching in chat:
# /model - Switch LLM model mid-conversation
# /add_toolkit - Load toolkit from .alita/tools/*.json
# /add_mcp - Add MCP server from .alita/mcp.json
# /dir - Mount additional directory
```

### Creating a New Toolkit
1. Create `alita_sdk/tools/mytool/__init__.py`:
   ```python
   class MyToolkit(BaseToolkit):
       @staticmethod
       def toolkit_config_schema() -> BaseModel:
           return create_model('mytool',
               url=(str, Field(description="API URL")),
               api_key=(SecretStr, Field(json_schema_extra={'secret': True})),
               selected_tools=(List[...], Field(default=[]))
           )
       
       @classmethod
       def get_toolkit(cls, selected_tools=None, toolkit_name=None, **kwargs):
           wrapper = MyApiWrapper(**kwargs)
           tools = []
           for tool in wrapper.get_available_tools():
               if selected_tools and tool['name'] not in selected_tools:
                   continue
               tools.append(BaseAction(
                   api_wrapper=wrapper,
                   name=tool['name'],
                   description=tool['description'],
                   args_schema=tool['args_schema']
               ))
           return cls(tools=tools)
   ```
2. Create `api_wrapper.py` with tool implementations
3. Register in `alita_sdk/tools/__init__.py`
4. Add config to `alita_sdk/configurations/mytool.py` if using platform

## Critical Patterns

### Toolkit Configuration Loading
- Toolkits configured via JSON/YAML files in `.alita/tools/`
- [toolkit_loader.py](../alita_sdk/cli/toolkit_loader.py) loads configs with env var substitution (`${VAR}`)
- Schema defined by `toolkit_config_schema()` in each toolkit's `__init__.py`
- Example: [.alita/tests/test_pipelines/configs/github_toolkit.json](../.alita/tests/test_pipelines/configs/)

### Filesystem Tools Security
[cli/tools/filesystem.py](../alita_sdk/cli/tools/filesystem.py) - All file operations sandboxed to `base_directory`:
- **Presets:** `readonly`, `safe` (no delete), `full`, `basic`, `minimal`
- Multi-directory support via `allowed_directories` parameter
- Path validation in `_resolve_path()` blocks traversal attacks
- Custom tool selection: `include_tools`, `exclude_tools`

### Agent Execution Flow
1. `Assistant.__init__()` - Initialize with tools, memory, LLM
2. `create_graph()` - Build LangGraph with nodes (tools, LLM, etc.)
3. `LangGraphAgentRunnable` - Compiled state graph executor
4. Agents support `app_type`: `agent` (React), `pipeline` (graph workflow), `predict` (no memory)

### Testing Toolkits
The declarative test framework lives in `.alita/tests/test_pipelines/`. Run tests with:
```bash
.alita/tests/test_pipelines/run_test.sh --local suites/github_toolkit GH04
```
See [test_pipelines README](../.alita/tests/test_pipelines/README.md) for full documentation.

## Environment Setup

Required `.env` (or `.alita/.env`):
```bash
DEPLOYMENT_URL=https://your-deployment.elitea.ai
API_KEY=your_api_key
PROJECT_ID=your_project_id
OPENAI_API_KEY=sk-...  # For LLM access

# Toolkit credentials (optional)
GITHUB_TOKEN=ghp_...
JIRA_TOKEN=...
```

Override: `export ALITA_ENV_FILE=/path/to/.env`

## Common Commands

```bash
# Install with all dependencies
pip install -U '.[all]'

# List available toolkits
alita-cli toolkit list

# Test specific toolkit tool
alita-cli toolkit test github --tool get_issue --config .alita/tools/github.json --param repo=owner/repo --param issue_number=1

# Run agent with planning tools
alita-cli agent chat planner --plan
```
## Project Conventions

- **Agent type:** `react` (default, LangGraph React), `pipeline` (graph workflow), `predict` (stateless)
- **Persona:** `quirky`, `nerdy`, `cynical`, `generic` - affects system prompt tone
- **Lazy tools mode:** `lazy_tools_mode: true` reduces tokens by using meta-tools
- **Swarm mode:** Multi-agent collaboration with `internal_tools: ['swarm']`
- **Test naming:** `<SUITE><NN>` (e.g., `GH04` for GitHub toolkit test 4)
