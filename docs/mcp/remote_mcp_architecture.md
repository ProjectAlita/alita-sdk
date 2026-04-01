# Remote MCP Server Architecture — Alita/Elitea SDK

> Research compiled from full source analysis of `alita_sdk/runtime/utils/`, `alita_sdk/runtime/toolkits/`, `alita_sdk/runtime/clients/`, `alita_sdk/runtime/tools/`, and `alita_sdk/cli/`.

---

## Overview: Two Distinct MCP Pathways

The SDK implements **two parallel architectures** for MCP:

| Path | Toolkit Class | Transport | Usage Context |
|------|---------------|-----------|---------------|
| **Platform MCP** (`type: mcp`) | `McpToolkit` | HTTP/SSE → `langchain-mcp-adapters` | Platform-provisioned, OAuth-capable |
| **Config MCP** (`type: mcp_config`) | `McpConfigToolkit` | stdio subprocess or HTTP | Pre-configured YAML registry (server-side) |
| **CLI MCP** (`toolkit_type: mcp`) | `MultiServerMCPClient` | stdio or `streamable_http` | CLI `.alita/mcp.json` workspace |

---

## 1. Remote MCP Server Architecture

### Configuration Files

#### `.alita/mcp.json` — CLI Workspace Config (VSCode-compatible format)

```json
{
  "mcpServers": {
    "github": {
      "type": "streamable_http",
      "url": "https://api.githubcopilot.com/mcp/",
      "headers": {
        "Authorization": "Bearer ${GIT_TOOL_ACCESS_TOKEN}"
      }
    }
  }
}
```

Supports:
- `type: stdio` + `command` → local subprocess
- `type: streamable_http` / `type: http` + `url` → remote HTTP
- `selected_tools` / `excluded_tools` for per-server tool filtering
- `stateful: true` for stateful servers (e.g. Playwright)
- `env` object for environment variable injection

Environment variable substitution is applied via `substitute_env_vars(content)` at load time (`cli/mcp_loader.py:44`).

#### Platform Toolkit Config (stored in DB / passed via `toolkit_configs`)

```json
{
  "type": "mcp",
  "toolkit_name": "my-server",
  "settings": {
    "url": "https://mcp-server.example.com/mcp",
    "headers": {"Authorization": "Bearer ..."},
    "session_id": "uuid",
    "ssl_verify": true,
    "timeout": 300,
    "selected_tools": []
  }
}
```

#### Server-side YAML — `mcp_servers.yml` / Pylon config

Loaded by `McpConfigToolkit` from `ALITA_MCP_SERVERS_CONFIG` env var or `/data/plugins/indexer_worker/config.yml`:

```yaml
mcp_servers:
  playwright:
    type: stdio
    command: npx
    args: ["@playwright/mcp@latest"]
    stateful: true
    description: "Browser automation via Playwright"

  github_copilot:
    type: http
    url: "https://api.githubcopilot.com/mcp/"
    headers:
      Authorization: "Bearer {github_token}"
    config_schema:
      properties:
        github_token:
          type: string
          secret: true
          required: true
```

`{param}` placeholders (single-brace) are substituted from `user_config` at runtime via `substitute_mcp_placeholders()` (`mcp_oauth.py:206`). `{{secret}}` double-brace patterns are resolved at the platform level before the SDK receives the config.

### Data Models

**`McpConnectionConfig`** (`runtime/models/mcp_models.py:11`):

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `url` | `str` | required | HTTP/HTTPS MCP server URL |
| `headers` | `Optional[Dict[str, str]]` | `None` | Auth/config headers |
| `session_id` | `Optional[str]` | `None` | Stateful SSE session ID |
| `ssl_verify` | `bool` | `True` | SSL certificate verification |

**`McpToolkitConfig`** (`mcp_models.py:47`): wraps `McpConnectionConfig` + `timeout`, `selected_tools`, `enable_caching`, `cache_ttl`.

**`McpToolMetadata`** (`mcp_models.py:58`): `name`, `description`, `server`, `input_schema`, `enabled`.

### Platform MCP Connection Lifecycle

```
McpToolkit.get_toolkit()                      [mcp.py:179]
  └─ McpConnectionConfig(url, headers, session_id, ssl_verify)
  └─ _create_tools_from_server()              [mcp.py:280]
       └─ _discover_tools_sync()              [mcp.py:370]
            └─ asyncio.run(_discover_tools_async())  [mcp.py:390]
                 └─ UnifiedMcpClient(url, ...)       [mcp_adapter.py:41]
                      └─ _connect()                  [mcp_adapter.py:93]
                           ├─ _preflight_auth_check()  → 401 detection
                           ├─ _detect_transport()      → sse | streamable_http
                           ├─ _build_server_config()
                           └─ MultiServerMCPClient({name: config})
                                └─ session_context.__aenter__()  → persistent session
                      └─ initialize()               [mcp_adapter.py:441]
                      └─ list_tools()               [mcp_adapter.py:462]
                      └─ (list_prompts if available) [mcp.py:470]
  └─ _create_tool_from_dict() → McpRemoteTool      [mcp.py:507]
```

### Difference: Local (stdio) vs Remote (HTTP/SSE)

| Aspect | stdio (local) | HTTP/SSE (remote) |
|--------|---------------|-------------------|
| Transport | subprocess stdin/stdout | `streamable_http` or `sse` |
| Auth | env vars, no OAuth | Bearer token / OAuth PKCE flow |
| Session | fresh per call (`asyncio.run`) | persistent `mcp-session-id` header |
| Library | `mcp.ClientSession` + `stdio_client` | `langchain-mcp-adapters` `MultiServerMCPClient` |
| Config key | `type: stdio`, `command:` | `type: streamable_http`, `url:` |
| Stateful support | fresh subprocess each call | server-provided `mcp-session-id` header |

---

## 2. Authentication & OAuth Flow

### Key Files
- `alita_sdk/runtime/utils/mcp_oauth.py` — all OAuth utilities
- `alita_sdk/runtime/utils/mcp_adapter.py` — pre-flight 401 detection

### `McpAuthorizationRequired` Exception (`mcp_oauth.py:13`)

Extends `ToolException`. Carries:

| Field | Description |
|-------|-------------|
| `server_url` | Canonical URL (`canonical_resource()`) |
| `resource_metadata_url` | RFC9728 protected resource metadata URL |
| `www_authenticate` | Raw `WWW-Authenticate` header value |
| `resource_metadata` | Dict with `authorization_servers`, scopes |
| `status` | Always `401` |
| `tool_name` | MCP server URL |

### OAuth Detection Chain (`mcp_adapter.py:213–423`)

```
UnifiedMcpClient._preflight_auth_check()
  POST {url}  ← JSON-RPC initialize request via aiohttp
  if response.status == 401:
    _handle_401_response(response)
      parse WWW-Authenticate header
      if configured_auth=True → raise ValueError   (static credentials are bad)
      else:
        1. extract_authorization_uri(www_authenticate)      → direct OAuth server URL
        2. extract_resource_metadata_url(www_authenticate)  → RFC9728 link
        3. fetch_oauth_authorization_server_metadata(auth_uri)
           OR fetch_resource_metadata_async(resource_metadata_url)
           OR infer_authorization_servers_from_realm(www_authenticate, url)
        → raise McpAuthorizationRequired(server_url, resource_metadata, ...)
  if response.status == 400 and configured_auth → raise ValueError
```

The pre-flight check uses `aiohttp` directly (not `langchain-mcp-adapters`) because `langchain-mcp-adapters` wraps exceptions in `ExceptionGroup`, losing the raw HTTP response needed to extract OAuth metadata from the `WWW-Authenticate` header.

### `configured_auth` Flag

Distinguishes two 401 scenarios:

| `configured_auth` | Meaning | Action |
|-------------------|---------|--------|
| `True` | `Authorization` header was in DB toolkit settings | Raise `ValueError` — user must fix credentials |
| `False` | No pre-configured auth | Raise `McpAuthorizationRequired` — trigger OAuth flow |

Set in `mcp.py:441` and `client.py:1882`.

### OAuth Token Exchange (`mcp_oauth.py:250`)

Server-side token exchange (avoids browser CORS):

```python
exchange_oauth_token(
    token_endpoint,   # From OAuth server metadata
    code,             # Authorization code from callback
    redirect_uri,
    client_id,        # Optional for DCR/public clients
    client_secret,    # Optional for public clients
    code_verifier,    # PKCE verifier
    scope,
)
# → POST application/x-www-form-urlencoded
# → Returns {access_token, refresh_token, expires_in, ...}
```

### Token Refresh (`mcp_oauth.py:546`)

```python
refresh_oauth_token(
    token_endpoint, refresh_token,
    client_id, client_secret, scope
)
# → POST grant_type=refresh_token
```

### OAuth Metadata Discovery (`mcp_oauth.py:82`)

Tries discovery endpoints in order:
1. Direct `/.well-known/` URL if already provided
2. `{base_url}/.well-known/oauth-authorization-server`
3. `{base_url}/.well-known/openid-configuration`
4. Any `extra_endpoints` supplied by caller

### Token Injection Flow (platform path, `runtime/toolkits/tools.py:295`)

```python
# 1. canonical_resource(url) → normalized URL key
# 2. token_data = mcp_tokens.get(canonical_url)
# 3. access_token = token_data['access_token']
# 4. session_id  = token_data['session_id']
# 5. headers['Authorization'] = f'Bearer {access_token}'
# 6. settings['session_id'] = session_id
McpToolkit.get_toolkit(..., **settings)
```

`mcp_tokens` format: `{canonical_url: {access_token: str, session_id: str}}` (or legacy plain string).

### `ignored_mcp_servers` (`tools.py:304`)

When the user clicks "Continue without authentication", the frontend passes the canonical server URL in `ignored_mcp_servers`. The SDK skips that toolkit entirely:

```python
if canonical_url in ignored_mcp_servers or url in ignored_mcp_servers:
    continue  # Skip this MCP server
```

### Placeholder Substitution (`mcp_oauth.py:206`)

```python
substitute_mcp_placeholders({"Authorization": "Bearer {github_token}"}, user_config)
# Replaces {param} single-brace patterns from user_config
# Skips {{secret}} double-brace patterns (resolved at platform level)
```

---

## 3. Transport Layer

### Transport Auto-Detection (`mcp_adapter.py:152`)

```python
def _detect_transport(self) -> str:
    if self.transport != "auto":
        return self.transport           # Explicit override
    if url.rstrip('/').endswith('/sse'):
        return "sse"                    # Legacy SSE endpoint
    if url.startswith('http://') or url.startswith('https://'):
        return "streamable_http"        # Default for HTTP URLs
    return "streamable_http"            # Fallback
```

### Transport Config for `langchain-mcp-adapters`

**Remote HTTP (streamable_http / sse):**
```python
config = {
    'transport': 'streamable_http',   # or 'sse'
    'url': url,
    'headers': headers,               # Auth headers
    'httpx_client_factory': ...,      # Only when ssl_verify=False
}
```

**Local stdio:**
```python
config = {
    'transport': 'stdio',
    'command': server_command,
    'args': server_args,
    'env': server_env,                # Optional environment vars
}
```

### SSL Verification Bypass (`mcp_adapter.py:198`)

When `ssl_verify=False`, a custom `httpx_client_factory` is passed to `langchain-mcp-adapters`:

```python
def _create_insecure_httpx_client(self, headers=None, timeout=None, auth=None):
    return httpx.AsyncClient(
        headers=headers, timeout=timeout, auth=auth,
        verify=False
    )
```

SSL is also disabled in the pre-flight `aiohttp` connector:
```python
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE
connector = aiohttp.TCPConnector(ssl=ssl_context)
```

### WebSocket Support

Not implemented. Supported transports: `stdio`, `sse`, `streamable_http`.

### `ExceptionGroup` Unwrapping (`mcp_adapter.py:124`)

`langchain-mcp-adapters` uses `asyncio.TaskGroup` internally, which wraps exceptions in Python 3.11+ `ExceptionGroup`. The adapter unwraps them:

```python
except BaseException as e:
    if hasattr(e, 'exceptions') and e.exceptions:
        inner = e.exceptions[0]
        # Check for auth-related errors
        if self.configured_auth and any(
            kw in str(inner).lower() for kw in ['401', 'unauthorized', 'forbidden', ...]
        ):
            raise ValueError("Authorization credentials are invalid...") from inner
        raise inner from e
```

---

## 4. Tool Discovery & Registration

### Platform Discovery Path

```
McpToolkit._discover_tools_sync()                [mcp.py:370]
  asyncio.run(_discover_tools_async())            [mcp.py:410]
    UnifiedMcpClient.__aenter__ → _connect()     [mcp_adapter.py:84]
    client.list_tools()                          [mcp_adapter.py:462]
      langchain_mcp_adapters.tools.load_mcp_tools(session, connection, server_name)
      → convert to dicts: {name, description, inputSchema}
    client.list_prompts() (optional)             [mcp.py:470]
      → converts to tool dict with _mcp_type="prompt", _mcp_prompt_name=...
    Returns (tool_list, server_session_id)

_create_tool_from_dict()                         [mcp.py:507]
  McpServerTool.create_pydantic_model_from_schema(inputSchema)  [mcp_server_tool.py:26]
    → parses JSON Schema → Pydantic model with typed fields
    handles: string, integer, number, boolean, object, array
    handles: enum → Literal, email → EmailStr, pattern → StringConstraints
    handles: anyOf/oneOf, allOf, nullable types (Optional[T])
  McpRemoteTool(                                 [mcp_remote_tool.py:33]
    name, description, args_schema,
    server_url, server_headers,
    session_id, ssl_verify,
    original_tool_name,   ← preserves original name for MCP invocation
    metadata={"toolkit_name": ..., "toolkit_type": "mcp"}
  )
```

### CLI Discovery Path

```
cli/mcp_loader.py: load_mcp_tools()              [mcp_loader.py:61]
  reads mcp.json → build toolkit_config per server
  returns [{toolkit_type: 'mcp', name:, mcp_server_config: {...}}]

cli/agent_executor.py: create_agent_executor_with_mcp()  [agent_executor.py:97]
  load_mcp_tools_async(mcp_configs)              [mcp_loader.py:216]
    MultiServerMCPClient({server_name: config})
    for each server:
      session_context = client.session(server_name)
      session = await session_context.__aenter__()   ← PERSISTENT session
      tools = await load_mcp_tools(session, connection=..., server_name=...)
    Returns (MCPSessionManager, all_langchain_async_tools)
```

### JSON Schema → Pydantic Type Mapping (`mcp_server_tool.py:26`)

| JSON Schema type | Python type |
|-----------------|-------------|
| `string` | `str` |
| `string` + `enum` | `Literal[...]` |
| `string` + `format: email` | `EmailStr` |
| `string` + `pattern` | `Annotated[str, StringConstraints(pattern=...)]` |
| `integer` | `int` |
| `number` | `float` |
| `boolean` | `bool` |
| `object` | Nested Pydantic model |
| `array` | `List[T]` |
| `anyOf` / `oneOf` with `null` | `Optional[T]` |
| `allOf` | Merged Pydantic model |

### Tool Registration in LangGraph Agent

- **Platform tools** → `McpRemoteTool` instances → `Assistant.__init__(tools=...)` → `create_graph()` → LangGraph `ToolNode`
- **CLI tools** → raw `langchain-mcp-adapters` async tools → `additional_tools` list → `_create_assistant()` → LangGraph `ToolNode`
- **Metadata injection** (`tools.py:596–604`): `toolkit_type: 'mcp'`, `toolkit_name`, `display_name`

### Static Fallback Discovery (`mcp.py:558`)

If live discovery fails and an `AlitaClient` is present:

```python
client.get_mcp_toolkits()
# → GET /api/v2/elitea_core/tools_list/{project_id}
# → Returns platform-registered tool schemas
```

---

## 5. CLI Integration

### File: `alita_sdk/cli/mcp_loader.py`

#### `load_mcp_config(file_path)` — line 24
- Reads `.alita/mcp.json`
- Applies `substitute_env_vars(content)` (e.g. `${GIT_TOOL_ACCESS_TOKEN}`)
- Validates `mcpServers` key; returns `{}` gracefully if file missing

#### `load_mcp_tools(agent_def, mcp_config_path)` — line 61
- Reads `agent_def['mcps']` — list of server names (`str`) or `{name, selected_tools, excluded_tools}` dicts
- Merges agent-level overrides with server-level defaults (agent takes precedence)
- Returns `[{toolkit_type: 'mcp', name:, mcp_server_config: {...}}]`

#### `MCPSessionManager` — line 196
Holds `client` and `sessions` dict alive for entire agent lifetime. Required to maintain stateful MCP server state (e.g. Playwright browser). See [langchain-mcp-adapters#178](https://github.com/langchain-ai/langchain-mcp-adapters/issues/178).

#### `load_mcp_tools_async(mcp_toolkit_configs)` — line 216
- Creates `MultiServerMCPClient({server_name: config})`
- For each server: `session_context.__aenter__()` → **persistent session**
- Calls `langchain_mcp_adapters.tools.load_mcp_tools(session, ...)`
- Returns `(MCPSessionManager, all_tools)`

### CLI Commands (`agents.py`)

| Command | Action |
|---------|--------|
| `/add_mcp` | Interactive menu from `mcp.json` → appends to `agent_def['mcps']` → reinitializes executor |
| `/rm_mcp [name]` | Removes from `agent_def['mcps']` → reinitializes executor |

Agent definition (`*.agent.md` YAML frontmatter) can declare `mcps:` for preloaded MCP servers at startup.

### Agent Execution with MCP (`agents.py:408–437`)

```python
has_mcp = any(tc.get('toolkit_type') == 'mcp' for tc in toolkit_configs)
if has_mcp:
    # Create a PERSISTENT event loop for MCP tools (stored on LLMNode)
    LLMNode._persistent_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    agent_executor, mcp_session_manager = loop.run_until_complete(
        create_agent_executor_with_mcp(...)
    )
```

The persistent loop is essential — all MCP async tool calls run on it throughout the agent's lifetime.

---

## 6. Platform Integration (AlitaClient)

### File: `alita_sdk/runtime/clients/client.py`

#### Platform API Endpoints (lines 101–102)

```python
mcp_tools_list = f"{base_url}/api/v2/elitea_core/tools_list/{project_id}"
mcp_tools_call = f"{base_url}/api/v2/elitea_core/tools_call/{project_id}"
```

#### `get_mcp_toolkits()` — line 119

```
GET /api/v2/elitea_core/tools_list/{project_id}
→ JSON list of registered MCP server toolkits + tool schemas
```

Used as static fallback when live discovery fails.

#### `mcp_tool_call(params)` — line 123

```
POST /api/v2/elitea_core/tools_call/{project_id}
Body: {
  server:           str,
  tool_timeout_sec: int,
  tool_call_id:     str (UUID),
  params: {
    name:      str,
    arguments: dict
  }
}
```

Used by `McpServerTool._run()` (base class) — legacy path before `McpRemoteTool` override.

#### `test_mcp_connection(toolkit_config, mcp_tokens)` — line 1816

Full connection validation method:
1. Extracts `url`, `headers`, `session_id` from `settings`
2. Sets `configured_auth=True` if static `Authorization` header present
3. Applies OAuth token from `mcp_tokens` dict if available
4. Creates `UnifiedMcpClient`, calls `initialize()` + `list_tools()`
5. Returns `{success, tools, tools_count, transport, server_session_id}`
6. Raises `McpAuthorizationRequired` if OAuth needed

#### `application()` method — line 730

Passes `mcp_tokens`, `ignored_mcp_servers`, `conversation_id` through to `Assistant` construction → `create_graph()` → tool initialization.

---

## 7. Additional Infrastructure

### `McpDiscoveryClient` (`runtime/clients/mcp_discovery.py`)

Background-polling discovery service:
- 5-minute default discovery interval
- 10-minute cache TTL
- Sends raw `tools/list` JSON-RPC POSTs (not using `langchain-mcp-adapters`)
- Supports `STATIC`, `DYNAMIC`, `HYBRID` modes via `McpManager`
- Used by `McpManager`/`McpDiscoveryService` — lower-level infrastructure, not in main hot path

### `McpManager` (`runtime/clients/mcp_manager.py`)

Discovery modes:

| Mode | Strategy |
|------|----------|
| `STATIC` | `client.get_mcp_toolkits()` (platform registry) |
| `DYNAMIC` | Live query via `McpDiscoveryClient` |
| `HYBRID` | Dynamic first, static fallback |

### `McpConfigToolkit` (`runtime/toolkits/mcp_config.py`)

Pre-configured server toolkit loaded from YAML:
- `type: stdio` → `_load_stdio_tools_async()` — MCP SDK `stdio_client` + `ClientSession`, fresh subprocess per tool call via `_create_stdio_tool_func()`
- `type: http` → delegates to `McpToolkit._load_http_tools()`
- Config paths checked (priority order): Pylon plugin config → `ALITA_MCP_SERVERS_CONFIG` env → `/data/plugins/indexer_worker/config.yml` → `/data/configs/indexer_worker.yml`

### `McpInspectTool` (`runtime/tools/mcp_inspect_tool.py`)

Internal server inspection tool (not added to agents):
- Calls `tools/list`, `prompts/list`, `resources/list` via raw `aiohttp`
- Handles both JSON and SSE (`text/event-stream`) response content types
- Used for internal toolkit exploration; commented out from agent tool registration

---

## 8. Complete Call Chains

### Platform MCP Tool Execution

```
LangGraph ToolNode
  → McpRemoteTool._run()                      [mcp_remote_tool.py:81]
  → ThreadPoolExecutor + _run_in_new_loop()
  → asyncio.run(_execute_remote_tool())        [mcp_remote_tool.py:102]
  → UnifiedMcpClient(url, session_id, headers) [mcp_adapter.py:41]
  → _preflight_auth_check()                    [mcp_adapter.py:213]
  → _connect() → MultiServerMCPClient         [mcp_adapter.py:93]
  → client.call_tool(tool_name, kwargs)        [mcp_adapter.py:514]
      load_mcp_tools(session, ...) → find tool
      tool.ainvoke(clean_args)                 ← None args stripped
  → HTTP POST to MCP server
  → format content[] → str result
```

### CLI MCP Tool Execution

```
LangGraph ToolNode
  → langchain-mcp-adapters async tool.ainvoke()
  → MCP session (PERSISTENT, kept alive in MCPSessionManager)
  → HTTP POST to MCP server (streamable_http)
  OR → subprocess stdin/stdout pipe (stdio)
```

### OAuth Flow (when `McpAuthorizationRequired` raised)

```
McpRemoteTool._run() or McpToolkit.get_toolkit()
  → McpAuthorizationRequired raised with resource_metadata
  → Propagated to LangGraph tool exception handler
  → Frontend receives exception.to_dict()
  → Frontend opens browser popup to authorization_servers[0] auth URL
  → User authorizes → callback with code + state
  → exchange_oauth_token(token_endpoint, code, redirect_uri, code_verifier)  [mcp_oauth.py:250]
  → access_token stored as mcp_tokens[canonical_url]
  → Next request: token injected into headers via mcp_tokens lookup (tools.py:314)
```

### `McpAuthorizationRequired` → Resource Metadata Discovery

```
_handle_401_response(response)                 [mcp_adapter.py:303]
  www_auth = response.headers['WWW-Authenticate']
  
  Path A: authorization_uri= in header
    fetch_oauth_authorization_server_metadata(authorization_uri)
    → metadata['authorization_servers'] = [issuer]
  
  Path B: resource_metadata= (RFC9728) in header
    fetch_resource_metadata_async(resource_metadata_url)
    → metadata = {authorization_servers: [...], ...}
    fetch_oauth_authorization_server_metadata(auth_server)
    → metadata['oauth_authorization_server'] = {...}
  
  Path C: infer from realm / server URL
    infer_authorization_servers_from_realm(www_auth, url)
    → base_url from parsed server URL
    fetch_oauth_authorization_server_metadata(base_url)
  
  raise McpAuthorizationRequired(server_url, resource_metadata=metadata, ...)
```

---

## 9. Error Handling (`mcp_oauth.py:336`)

`extract_user_friendly_mcp_error(exception, headers)` maps raw exceptions to user-friendly messages:

| Error type | Message |
|-----------|---------|
| `McpAuthorizationRequired` | "MCP server requires authorization..." |
| JSON-RPC `-32700` | "Parse error: ..." |
| JSON-RPC `-32601` | "Method not found: ..." |
| HTTP 401 (with auth) | "Authentication failed. Your credentials... invalid or expired." |
| HTTP 401 (no auth) | "Authentication required. Please provide valid credentials..." |
| HTTP 403 | "Access forbidden..." |
| HTTP 404 | "MCP server endpoint not found (404)..." |
| SSL errors | "SSL certificate verification failed..." |
| Timeout | "Connection to MCP server timed out..." |
| DNS failure | "DNS resolution failed..." |

---

## 10. Key File Reference

| File | Purpose |
|------|---------|
| `runtime/utils/mcp_oauth.py` | OAuth utilities: `McpAuthorizationRequired`, token exchange/refresh, metadata discovery, error formatting |
| `runtime/utils/mcp_adapter.py` | `UnifiedMcpClient`: transport detection, pre-flight 401, `langchain-mcp-adapters` wrapper |
| `runtime/utils/mcp_tools_discovery.py` | Standalone `discover_mcp_tools()` sync/async helper |
| `runtime/toolkits/mcp.py` | `McpToolkit`: platform remote MCP toolkit, full discovery + tool creation |
| `runtime/toolkits/mcp_config.py` | `McpConfigToolkit`: YAML-configured stdio/http MCP servers |
| `runtime/tools/mcp_server_tool.py` | `McpServerTool`: base tool class, JSON Schema → Pydantic, platform `mcp_tool_call` |
| `runtime/tools/mcp_remote_tool.py` | `McpRemoteTool`: remote HTTP/SSE tool invocation via `UnifiedMcpClient` |
| `runtime/tools/mcp_inspect_tool.py` | `McpInspectTool`: internal server introspection (tools/prompts/resources) |
| `runtime/clients/client.py` | `AlitaClient`: `get_mcp_toolkits()`, `mcp_tool_call()`, `test_mcp_connection()` |
| `runtime/clients/mcp_discovery.py` | `McpDiscoveryClient`: background-polling discovery with cache |
| `runtime/clients/mcp_manager.py` | `McpManager`: STATIC/DYNAMIC/HYBRID discovery modes |
| `runtime/models/mcp_models.py` | `McpConnectionConfig`, `McpToolkitConfig`, `McpToolMetadata` |
| `runtime/toolkits/tools.py` | `instantiate_toolkit_with_client()`: routes `type: mcp` and `type: mcp_config`, injects OAuth tokens |
| `cli/mcp_loader.py` | `load_mcp_config()`, `load_mcp_tools()`, `MCPSessionManager`, `load_mcp_tools_async()` |
| `cli/agents.py` | `/add_mcp`, `/rm_mcp` commands; `_setup_local_agent_executor()` with MCP path |
| `cli/agent_executor.py` | `create_agent_executor_with_mcp()`: persistent loop + session setup |
| `.alita/mcp.json` | CLI workspace MCP server configuration |
