# Agent Definition Format

Agent definitions use Markdown files with YAML frontmatter. This format allows you to configure agent behavior, model settings, tools, and more.

## Basic Structure

```markdown
---
name: my-agent
model: gpt-4o
temperature: 0.7
---
Your system prompt goes here...
```

## Complete Frontmatter Options

### Core Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | string | (filename) | Agent name |
| `description` | string | "" | Agent description |
| `model` | string | gpt-4o | LLM model to use |
| `temperature` | float | 0.1 | Model temperature (0.0-2.0) |
| `max_tokens` | integer | 4096 | Maximum tokens per response |

### Agent Behavior

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `agent_type` | string | react | Agent type: `react`, `pipeline`, `predict` |
| `persona` | string | quirky | Response style: `quirky`, `nerdy`, `cynical`, `generic` |
| `step_limit` | integer | 25 | Maximum tool execution steps per turn |
| `lazy_tools_mode` | boolean | false | Enable lazy tool discovery (uses meta-tools for large toolsets) |
| `internal_tools` | array | [] | Internal tools for multi-agent workflows: `['swarm']` |

### Tool Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `tools` | array | [] | List of tool/toolkit names to enable |
| `toolkit_configs` | array | [] | Toolkit configuration references |

#### Toolkit Configs Format

```yaml
toolkit_configs:
  - file: .alita/tools/github.json      # Load from file
  - type: jira                            # Direct config
    url: https://jira.example.com
    api_key: ${JIRA_TOKEN}
```

### Filesystem Tools

Control which filesystem operations the agent can perform:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `filesystem_tools_preset` | string | null | Preset: `readonly`, `safe`, `full`, `basic`, `minimal` |
| `filesystem_tools_include` | array | null | Specific tools to include |
| `filesystem_tools_exclude` | array | null | Specific tools to exclude |

**Presets:**
- `readonly`: Only read operations (list, read, search, info)
- `safe`: All except delete
- `full`: All filesystem tools
- `basic`: Read, write, append, list, create directory
- `minimal`: Only read and list

**Available Tools:**
- `filesystem_read_file` - Read complete file contents
- `filesystem_read_file_chunk` - Read file by line range
- `filesystem_read_multiple_files` - Batch read multiple files
- `filesystem_write_file` - Create/overwrite file
- `filesystem_append_file` - Append to file (incremental writing)
- `filesystem_edit_file` - Precise text replacement
- `filesystem_apply_patch` - Multiple edits in one operation
- `filesystem_list_directory` - List directory contents
- `filesystem_directory_tree` - Recursive tree view
- `filesystem_search_files` - Glob pattern search
- `filesystem_delete_file` - Delete files
- `filesystem_move_file` - Move/rename files
- `filesystem_create_directory` - Create directories
- `filesystem_get_file_info` - File metadata
- `filesystem_list_allowed_directories` - Show accessible paths

### MCP Integration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `mcps` | array | [] | MCP server names to load from `mcp.json` |

## Full Example

```markdown
---
name: code-reviewer
model: gpt-4o
temperature: 0.3
max_tokens: 8192
agent_type: react
persona: cynical
step_limit: 75
lazy_tools_mode: true
toolkit_configs:
  - file: .alita/tools/github.json
  - type: openai
    api_key: ${OPENAI_API_KEY}
filesystem_tools_preset: safe
mcps:
  - filesystem
  - browser
internal_tools: []
---
You are an expert code reviewer specializing in Python and TypeScript.

## Your Mission
Review code for:
- Security vulnerabilities
- Performance issues
- Code style consistency
- Best practices
- Test coverage

Be thorough but constructive in your feedback.
```

## Lazy Tools Mode

When `lazy_tools_mode: true`, the agent uses meta-tools to dynamically discover and select tools from large toolsets. This is useful when you have 50+ tools and want the agent to efficiently choose relevant ones.

**Benefits:**
- Reduces token usage by not binding all tools upfront
- Improves model performance with focused tool selection
- Better for agents with extensive capabilities

**When to use:**
- Agents with 20+ different toolkits
- General-purpose assistants with broad capabilities
- Multi-domain agents (code + docs + data + DevOps)

**Example:**
```yaml
---
name: polyglot-assistant
lazy_tools_mode: true
toolkit_configs:
  - file: .alita/tools/github.json
  - file: .alita/tools/jira.json
  - file: .alita/tools/confluence.json
  - file: .alita/tools/gitlab.json
  - file: .alita/tools/slack.json
  # ... many more toolkits
---
```

## Agent Types

### React Agent (`agent_type: react`)
**Default.** Reasoning + Acting loop with tool use.
- Iteratively reasons and takes actions
- Suitable for complex, multi-step tasks
- Uses memory and checkpointing

### Pipeline Agent (`agent_type: pipeline`)
Graph-based workflow execution.
- Follows predefined workflow in YAML
- Nodes, edges, conditional routing
- Ideal for structured processes

### Predict Agent (`agent_type: predict`)
Stateless single-shot inference.
- No memory, no tool execution
- Fast, lightweight responses
- Good for simple classification/extraction

## Environment Variables

Use `${VAR_NAME}` syntax in any string field:

```yaml
---
toolkit_configs:
  - type: github
    token: ${GITHUB_TOKEN}
  - type: jira
    url: ${JIRA_URL}
    api_key: ${JIRA_API_KEY}
---
```

Variables are substituted from environment at runtime.

## Best Practices

1. **Set appropriate step_limit**: Complex tasks may need 50+, simple tasks can use 25
2. **Use filesystem presets**: Start with `readonly` or `safe` for security
3. **Enable lazy mode for large toolsets**: Improves performance with 20+ tools
4. **Match persona to use case**: `cynical` for reviewers, `quirky` for assistants
5. **Document your prompts**: Clear instructions get better results
6. **Test with different temperatures**: Lower (0.1-0.3) for precision, higher (0.7-1.0) for creativity
7. **Use environment variables**: Keep credentials out of agent files

## CLI Usage

```bash
# Run agent
alita agent chat my-agent.agent.md

# Mount directory for filesystem access
alita agent chat my-agent.agent.md --dir ./project

# Override model/temperature
alita agent chat my-agent.agent.md --model gpt-4o --temperature 0.5

# Set step limit (overrides agent's step_limit)
alita agent chat my-agent.agent.md --recursion-limit 100

# Show tool execution
alita agent chat my-agent.agent.md -v default  # default verbosity
alita agent chat my-agent.agent.md -v debug    # verbose LLM calls
alita agent chat my-agent.agent.md -v quiet    # minimal output
```
