# MCP (Model Context Protocol) Toolkit

The MCP Toolkit enables Alita SDK to connect to a single remote MCP server and dynamically expose its tools within LangGraph agents. This toolkit provides a seamless way to integrate external tools and services following the [MCP specification](https://modelcontextprotocol.io/specification/2025-06-18).

## Overview

The MCP Toolkit consists of several key components:

- **McpToolkit**: Main toolkit class that manages a single MCP server connection and tool creation
- **McpConnectionConfig**: Configuration model for MCP server connection following the official specification
- **Dynamic Tool Creation**: Automatically generates Pydantic models from MCP tool schemas

## Features

- 🌐 **Single server focus**: Each toolkit instance connects to one MCP server
- 🔧 **Dynamic tool registration**: Automatically discover and register tools from the MCP server
- 📋 **MCP Specification Compliance**: Connection parameters follow the official MCP specification
- 💾 **Smart caching**: Cache tool schemas and responses with configurable TTL
- 🔄 **Error handling**: Robust error handling for connection and tool discovery issues
- 🎛️ **Flexible configuration**: Comprehensive configuration options following MCP standards

## Configuration

### Basic Configuration

```json
{
  "type": "mcp",
  "toolkit_name": "api_tools",
  "settings": {
    "server_name": "filesystem_server",
    "connection": {
      "url": "https://your-mcp-server.com/mcp",
      "headers": {
        "Authorization": "Bearer your-api-token",
        "X-Client-ID": "alita-sdk"
      }
    },
    "timeout": 60,
    "selected_tools": ["read_file", "write_file", "list_directory"],
    "enable_caching": true,
    "cache_ttl": 300
  }
}
```

### MCP Connection Configuration

The connection configuration follows the [MCP specification](https://modelcontextprotocol.io/specification/2025-06-18) for remote HTTP servers:

| Field | Type | Description | Required |
|-------|------|-------------|----------|
| `url` | string | MCP server HTTP/HTTPS URL | Yes |
| `headers` | object | HTTP headers for the connection (JSON object) | No |

### Toolkit Configuration Options

| Option | Type | Description | Default | Range |
|--------|------|-------------|---------|--------|
| `server_name` | string | MCP server name/identifier | - | Required |
| `connection` | object | MCP connection configuration | - | Required |
| `timeout` | integer | Request timeout in seconds | 60 | 1-300 |
| `selected_tools` | array | Specific tools to enable (empty = all) | [] | - |
| `enable_caching` | boolean | Enable tool schema caching | true | - |
| `cache_ttl` | integer | Cache TTL in seconds | 300 | 60-3600 |

## Usage Examples

### Example 1: File System Tools

Connect to a remote MCP server providing file system operations:

```json
{
  "type": "mcp",
  "toolkit_name": "filesystem_tools",
  "settings": {
    "server_name": "filesystem_server",
    "connection": {
      "url": "https://filesystem-mcp.example.com/api/mcp",
      "headers": {
        "Authorization": "Bearer fs-api-token",
        "X-Base-Path": "/workspace"
      }
    },
    "selected_tools": ["read_file", "write_file", "list_directory"],
    "timeout": 60,
    "enable_caching": true
  }
}
```

### Example 2: API Integration Server

Connect to an MCP server providing various API integrations:

```json
{
  "type": "mcp",
  "toolkit_name": "integration_tools",
  "settings": {
    "server_name": "api_integration_server",
    "connection": {
      "url": "https://integrations.example.com/mcp/v1",
      "headers": {
        "Authorization": "Bearer your-api-token",
        "X-Client-Version": "1.0.0",
        "X-Environment": "production"
      }
    },
    "timeout": 90,
    "enable_caching": true,
    "cache_ttl": 600
  }
}
```

### Example 3: Development Environment

Configuration for development with a local MCP server:

```json
{
  "type": "mcp",
  "toolkit_name": "dev_tools",
  "settings": {
    "server_name": "local_dev_server",
    "connection": {
      "url": "http://localhost:8080/mcp",
      "headers": {
        "X-Debug": "true"
      }
    },
    "timeout": 120,
    "enable_caching": false
  }
}
```

### Example 4: Database Tools

Connect to an MCP server providing database operations:

```json
{
  "type": "mcp",
  "toolkit_name": "database_tools",
  "settings": {
    "server_name": "database_server",
    "connection": {
      "url": "https://db-mcp.example.com/mcp",
      "headers": {
        "Authorization": "Bearer db-api-key",
        "X-Database": "production",
        "X-Schema": "public"
      }
    },
    "selected_tools": ["execute_query", "describe_table", "list_tables"],
    "timeout": 30,
    "cache_ttl": 180
  }
}
```

## Tool Naming

Tools from the MCP server are automatically prefixed to avoid naming conflicts:

- Format: `{toolkit_name}___{tool_name}` or `{server_name}___{tool_name}`
- The `___` separator (TOOLKIT_SPLITTER) is used consistently across Alita SDK
- Example: A tool named `read_file` from server `filesystem_server` becomes `filesystem_server___read_file`

## Error Handling

The MCP Toolkit provides robust error handling:

### Connection Errors
- Graceful degradation when the server is unavailable
- Clear error messages for connection issues
- Proper validation of connection parameters

### Tool Discovery Errors
- Failed tool discovery returns empty tool list
- Detailed logging for debugging connection and discovery issues
- Validation of tool schemas before tool creation

### Runtime Errors
- Tool execution errors are properly propagated to the agent
- Timeout handling with configurable per-toolkit timeouts
- Comprehensive error logging with context

## Tool Management

### Basic Usage

```python
from alita_sdk.runtime.toolkits import McpToolkit

# Create toolkit for a single remote MCP server
toolkit = McpToolkit.get_toolkit(
    server_name="filesystem_server",
    connection={
        "url": "https://filesystem-mcp.example.com/api/mcp",
        "headers": {"Authorization": "Bearer your-api-token"}
    },
    client=alita_client
)

# Get available tools
tools = toolkit.get_tools()
print(f"Available tools: {[tool.name for tool in tools]}")
```

### Tool Filtering

```python
# Create toolkit with specific tools only
toolkit = McpToolkit.get_toolkit(
    server_name="database_server",
    connection={
        "url": "https://db-mcp.example.com/mcp",
        "headers": {"Authorization": "Bearer db-api-key"}
    },
    selected_tools=["execute_query", "list_tables"],  # Only these tools
    client=alita_client
)
```

## Integration with LangGraph

The MCP Toolkit integrates seamlessly with LangGraph agents:

```python
from langgraph import StateGraph
from alita_sdk.runtime.toolkits import get_tools

# Configure MCP toolkit for a single remote server
mcp_config = {
    "type": "mcp",
    "toolkit_name": "filesystem_tools",
    "settings": {
        "server_name": "filesystem_server",
        "connection": {
            "url": "https://filesystem-mcp.example.com/api/mcp",
            "headers": {"Authorization": "Bearer your-api-token"}
        },
        "selected_tools": ["read_file", "write_file", "list_directory"]
    }
}

# Get tools
tools = get_tools([mcp_config], alita_client, llm)

# Create graph with MCP tools
graph = StateGraph(...)
for tool in tools:
    graph.add_node(f"tool_{tool.name}", tool)
```

## Best Practices

### 1. Server Selection
- Use one toolkit instance per MCP server for better isolation
- Choose appropriate server names that reflect the server's purpose
- Configure multiple toolkit instances if you need tools from different MCP servers

### 2. Connection Configuration
- Follow the MCP specification for HTTP connection parameters
- Always use HTTPS for production remote MCP servers
- Use HTTP only for development/testing on localhost
- Store sensitive information (tokens, passwords) in environment variables

### 3. Caching Strategy
- Enable caching for production environments to improve performance
- Use shorter cache TTLs for frequently changing tool schemas
- Disable caching in development for immediate schema updates

### 4. Error Handling
- Set appropriate timeouts based on your MCP server's response times
- Monitor error logs to identify connectivity issues
- Handle cases where the MCP server is temporarily unavailable

### 5. Tool Management
- Use `selected_tools` to filter and only enable the tools you need
- Choose meaningful `toolkit_name` values for tool prefixing
- Monitor tool execution performance and adjust timeouts as needed

### 6. Security
- Validate MCP server URLs and avoid user-controlled input
- Use proper authentication headers for HTTP-based MCP servers
- Avoid logging sensitive connection parameters

## Troubleshooting

### Common Issues

1. **Server Not Found**
   ```
   WARNING: MCP server 'my_server' not found in available toolkits
   ```
   - Verify the `server_name` matches the MCP server identifier in `alita.get_mcp_toolkits()`
   - Check if the MCP server is properly registered with the Alita client

2. **Connection Configuration Errors**
   ```
   ERROR: URL must use http:// or https:// scheme for remote MCP servers
   ```
   - Ensure the `connection.url` uses http:// or https:// schemes
   - Verify the URL includes proper host and port information
   - Use https:// for production servers, http:// only for localhost development

3. **Tool Schema Errors**
   ```
   ERROR: Failed to create MCP tool 'my_tool': schema validation error
   ```
   - Check if the tool's inputSchema is valid JSON Schema
   - Verify the MCP server is returning proper tool definitions

4. **Tool Discovery Issues**
   ```
   WARNING: Alita client does not support MCP toolkit discovery
   ```
   - Ensure your Alita client has the `get_mcp_toolkits()` method implemented
   - Verify the client is properly configured for MCP support

### Debug Mode

Enable debug logging to get detailed information:

```python
import logging
logging.getLogger('alita_sdk.runtime.toolkits.mcp').setLevel(logging.DEBUG)
```

## API Reference

### McpToolkit

The main toolkit class for MCP integration.

#### Methods

- `toolkit_config_schema()`: Returns the configuration schema following MCP specification
- `get_toolkit(server_name, connection, ...)`: Creates a configured toolkit instance for a single MCP server
- `get_tools()`: Returns list of available tools from the configured MCP server

#### Configuration Parameters

- `server_name` (str): MCP server name/identifier
- `connection` (dict): HTTP connection config with `url` and optional `headers`
- `timeout` (int): Request timeout in seconds (1-300)
- `selected_tools` (list): Specific tools to enable
- `enable_caching` (bool): Enable tool schema caching
- `cache_ttl` (int): Cache TTL in seconds (60-3600)

### McpConnectionConfig

Configuration model for remote HTTP MCP server connections following the official specification.

#### Fields

- `url` (str): MCP server HTTP/HTTPS URL (required)
- `headers` (dict, optional): HTTP headers for the connection (JSON object)

## Contributing

To contribute to the MCP Toolkit:

1. Follow the MCP specification when adding new features
2. Maintain the single-server-per-toolkit design principle
3. Add comprehensive tests for new functionality
4. Update documentation for any new features
5. Ensure backward compatibility with existing configurations

## License

The MCP Toolkit is part of the Alita SDK and follows the same licensing terms.

## References

- [Model Context Protocol Specification](https://modelcontextprotocol.io/specification/2025-06-18)
- [Alita SDK Documentation](https://github.com/ProjectAlita/alita-sdk)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)