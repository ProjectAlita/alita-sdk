# PyodideSandboxTool

The PyodideSandboxTool provides secure Python code execution using Pyodide (Python compiled to WebAssembly) within LangGraph React agents. This tool leverages the `langchain-sandbox` library to create a safe environment for running untrusted Python code.

## Features

- **🔒 Secure Execution**: Isolated environment with configurable permissions
- **💻 Local Execution**: No remote execution or Docker containers needed
- **🔄 Stateful Sessions**: Maintain state across multiple code executions
- **📦 Package Support**: Can install Python packages via Pyodide
- **⚡ Easy Integration**: Automatically added to React agents

## Installation

The sandbox tool requires `langchain-sandbox` which has been added to the runtime dependencies:

```bash
pip install langchain-sandbox
```

Note: `langchain-sandbox` requires Deno to be installed on the system. See [Deno installation guide](https://docs.deno.com/runtime/getting_started/installation/).

## Tool Variants

### 1. PyodideSandboxTool
Basic sandbox tool with configurable stateful mode.

```python
from alita_sdk.runtime.tools.sandbox import PyodideSandboxTool

tool = PyodideSandboxTool(stateful=True, allow_net=True)
```

### 2. StatefulPyodideSandboxTool
Always stateful version that preserves variables, imports, and function definitions across executions.

```python
from alita_sdk.runtime.tools.sandbox import StatefulPyodideSandboxTool

tool = StatefulPyodideSandboxTool(allow_net=True)
```

### 3. Factory Function
Convenient factory function for creating sandbox tools:

```python
from alita_sdk.runtime.tools.sandbox import create_sandbox_tool

# Non-stateful tool
tool1 = create_sandbox_tool(stateful=False, allow_net=True)

# Stateful tool
tool2 = create_sandbox_tool(stateful=True, allow_net=True)
```

## Automatic Integration

The sandbox tool is automatically added to React agents created with `getLangGraphReactAgent()`. The integration is done safely with graceful fallback if `langchain-sandbox` is not installed:

```python
# In assistant.py
def getLangGraphReactAgent(self):
    # ... existing code ...
    
    # Add sandbox tool by default for react agents
    try:
        from ..tools.sandbox import create_sandbox_tool
        sandbox_tool = create_sandbox_tool(stateful=True, allow_net=True)
        simple_tools.append(sandbox_tool)
        logger.info("Added PyodideSandboxTool to react agent")
    except ImportError as e:
        logger.warning(f"Failed to add PyodideSandboxTool: {e}. Install langchain-sandbox to enable this feature.")
    except Exception as e:
        logger.error(f"Error adding PyodideSandboxTool: {e}")
```

## Usage Examples

### Basic Code Execution

```python
tool = create_sandbox_tool(stateful=False)
result = tool._run("print('Hello, World!')")
# Output: Hello, World!
```

### Mathematical Calculations

```python
tool = create_sandbox_tool(stateful=False)
result = tool._run("""
import math
result = math.sqrt(16) + math.pi
print(f"Result: {result}")
result
""")
# Output: Result: 7.141592653589793
# Result: 7.141592653589793
```

### Stateful Execution

```python
tool = create_sandbox_tool(stateful=True)

# First execution - define variables
result1 = tool._run("x = 10; y = 20")

# Second execution - use previously defined variables
result2 = tool._run("sum_xy = x + y; print(f'Sum: {sum_xy}')")
# Output: Sum: 30
```

### Data Analysis

```python
tool = create_sandbox_tool(stateful=True, allow_net=True)

# Install and use data analysis libraries
result = tool._run("""
import numpy as np
data = np.array([1, 2, 3, 4, 5])
mean_value = np.mean(data)
print(f"Mean: {mean_value}")
mean_value
""")
```

## Tool Configuration

### Parameters

- **`stateful`** (bool, default: True): Whether to maintain state between executions
- **`allow_net`** (bool, default: True): Whether to allow network access for package installation

### Session Management

In stateful mode, the tool maintains:
- **Variables**: All defined variables persist
- **Imports**: Imported modules remain available
- **Functions**: User-defined functions are preserved
- **Classes**: Custom classes persist across calls

## Error Handling

The tool includes comprehensive error handling:

1. **Import Errors**: Graceful fallback if `langchain-sandbox` is not installed
2. **Execution Errors**: Captures and returns Python errors from the sandbox
3. **Timeout Handling**: Built-in execution timeouts
4. **Network Errors**: Handles network-related issues during package installation

## Output Format

The tool returns structured output including:

```
Result: <return_value>
Output: <stdout_content>
Error: <stderr_content>
Execution time: <time>s, Packages: <installed_packages>
```

## Limitations

- **Latency**: There's a few seconds of latency when starting the sandbox
- **File Access**: Currently not supported
- **Network Requests**: Use `httpx.AsyncClient` instead of `requests` for HTTP calls
- **System Access**: Limited system operations for security

## Security Considerations

The sandbox provides isolation from the host system:
- No direct file system access
- Limited system calls
- Configurable network access
- Memory and execution time limits

## Integration with LangGraph

The tool seamlessly integrates with LangGraph agents:

```python
from langgraph.prebuilt import create_react_agent
from alita_sdk.runtime.tools.sandbox import create_sandbox_tool

# Create agent with sandbox tool
sandbox_tool = create_sandbox_tool(stateful=True)
agent = create_react_agent(
    "your-llm-model",
    tools=[sandbox_tool],
    # ... other configuration
)
```

## Troubleshooting

### Common Issues

1. **"langchain-sandbox not installed"**
   ```bash
   pip install langchain-sandbox
   ```

2. **"Deno not found"**
   - Install Deno: https://docs.deno.com/runtime/getting_started/installation/

3. **Network access issues**
   - Ensure `allow_net=True` for package installation
   - Check firewall settings

4. **Execution timeouts**
   - Break large computations into smaller chunks
   - Use generators for long-running operations

### Debug Mode

Enable debug logging to troubleshoot issues:

```python
import logging
logging.getLogger('alita_sdk.runtime.tools.sandbox').setLevel(logging.DEBUG)
```

## Examples in Practice

See `demo_sandbox.py` for complete working examples and integration tests.