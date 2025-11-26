# Pipeline Nodes

## Code Node

The Code Node is a specialized node type in LangGraph agent pipelines that enables secure execution of Python code within a sandboxed environment. It provides a powerful way to integrate custom Python logic, data processing, and computational tasks directly into your agent workflows.

### Overview

The Code Node leverages Pyodide (Python compiled to WebAssembly) through the `langchain-sandbox` library to provide a secure, isolated environment for Python code execution. This ensures that code runs safely without access to the host system while maintaining full Python capabilities.

### Features

- **Secure Execution**: Code runs in an isolated Pyodide sandbox environment
- **State Integration**: Automatic injection of pipeline state variables into the code execution context
- **Performance Optimized**: Uses caching and stateless execution by default for better performance
- **Network Access**: Optional network access for package installation and external API calls
- **Flexible Output**: Support for structured output and custom variable mapping
- **Error Handling**: Comprehensive error handling and logging

### Configuration

#### Basic Configuration

```yaml
nodes:
  - id: "my_code_node"
    type: "code"
    code: 
      type: fixed
      value: |
          # Your Python code here
          result = 2 + 2
          print(f"The result is: {result}")
          {"calculation": result}
    input: ["messages"]
    output: ["calculation"]
    structured_output: true
```

#### Configuration Parameters

| Parameter | Type | Required | Default | Description                                                                                                        |
|-----------|------|----------|---------|--------------------------------------------------------------------------------------------------------------------|
| `id` | string | Yes | - | Unique identifier for the node                                                                                     |
| `type` | string | Yes | - | Must be "code"                                                                                                     |
| `code` | string | Yes | "'Code block is empty'" | Python code to execute: 'Code block is empty' will be returned                                                     |
| `output` | list[string] | No | [] | Output variables to store in pipeline state                                                                        |
| `structured_output` | boolean | No | false | Whether to parse output as structured data. `true` - will update state variables that matches to return statement* |

state **after** execution:
```yaml
user_name: "Bob"
user_score: 90
```
IMPORTANT: 
- Only variables listed in the `output` parameter will be updated in the state.
- Variables not listed in `state` **will be ignored** even if they are present in the returned dictionary.
- Output (non-messages) variables will be overrided with the result of tool execution or error message.
- Output variable `messages` will be set as an array of messages including any print statements and errors.


### Code Execution Environment

#### State Variables Access

The Code Node automatically injects the current pipeline state into the execution environment as `alita_state`. This allows your code to access and manipulate state variables:

```python
# Access pipeline state variables
previous_result = alita_state.get('previous_calculation', 0)

# Perform calculations
new_result = previous_result * 2

# Return results (will be stored in output variables)
{"doubled_result": new_result}
```

#### Available Libraries

The sandbox environment includes:
- Python standard library
- Common data processing libraries (can be installed dynamically)
- Network access for API calls (when enabled)
- JSON processing capabilities

#### Client Integration

When an Alita client is available, it's automatically injected as `alita_client` for API interactions:

```python
# Use the Alita client for API calls (list available artifacts from bucket `test`)
alita_client.list_artifacts(bucket_name='test')
```

### Output Handling

#### Output w or w/o output variables

- Results are stored in messages when `messages` is in output variables or when output variables are not defined:

```yaml
- id: "simple_code"
  type: "code"
  code: 
    type: fixed
    value: |
      "Hello, World!"
  # Output will be added to messages
```

- Results are stored in specified output variables when defined:

```yaml
- id: "output_variable_code"
  type: "code"
  code: 
    type: fixed
    value: |
      12345
  output: ["calculation_result"]
```
#### Structured Output

With `structured_output: true`, return dictionaries to update state variables:

```yaml
- id: "structured_code"
  type: "code"
  code: 
    type: fixed
    value: |
        {
          "user_name": "John Doe",
          "user_score": 95,
          "timestamp": "2024-01-01T00:00:00Z"
        }
  output: ["user_name", "user_score", "timestamp"]
  structured_output: true
```

\*  When `structured_output` is `true` and the code return a dictionary where keys may correspond to state variable names, then state variables matching those keys will be updated with the returned values.

_Example_:

state **before** execution:
```yaml
user_name: "Alice"
user_score: 85
```
code block:
```python
{
  "user_name": "Bob",
  "user_score": 90,
  "timestamp": "2024-01-01T00:00:00Z"
}
```

#### Output Variable Mapping

Specify which variables to extract from the code result:

```yaml
- id: "mapped_output"
  type: "code"
  code: 
    type: fixed
    value: |
        data = {"result": 42, "status": "success", "debug": "internal"}
        data
  output: ["result", "status"]  # Only these will be stored in state
  structured_output: true
```

### Use Cases

#### Data Processing

```yaml
- id: "process_data"
  type: "code"
  code: 
    type: fixed
    value: |
        import json
        
        # Access input data from state
        raw_data = alita_state.get('raw_data', [])
        
        # Process the data
        processed = []
        for item in raw_data:
            if item.get('score', 0) > 50:
                processed.append({
                    'id': item['id'],
                    'name': item['name'],
                    'grade': 'Pass'
                })
        
        {"processed_data": processed}
  input: ["raw_data"]
  output: ["processed_data"]
  structured_output: true
```

#### Mathematical Calculations

```yaml
- id: "calculate_metrics"
  type: "code"
  code: 
    type: fixed
    value: |
        import math
        
        values = alita_state.get('values', [])
        
        if not values:
            return {"error": "No values provided"}
        
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        std_dev = math.sqrt(variance)
        
        {
            "mean": mean,
            "variance": variance,
            "standard_deviation": std_dev,
            "count": len(values)
        }
  input: ["values"]
  output: ["mean", "variance", "standard_deviation", "count"]
  structured_output: true
```

#### API Integration

```yaml
- id: "external_api_call"
  type: "code"
  code: 
    type: fixed
    value: |
        import requests
        import json
        
        query = alita_state.get('search_query', '')
        
        try:
            response = requests.get(f"https://api.example.com/search?q={query}")
            data = response.json()
            
            {
                "api_results": data,
                "status": "success",
                "result_count": len(data.get('results', []))
            }
        except Exception as e:
            {
                "error": str(e),
                "status": "failed"
            }
  input: ["search_query"]
  output: ["api_results", "status", "result_count"]
  structured_output: true
```

#### Conditional Logic

```yaml
- id: "business_logic"
  type: "code"
  code: 
    type: fixed
    value: |
        user_age = alita_state.get('user_age', 0)
        user_type = alita_state.get('user_type', 'guest')
        
        # Business logic
        if user_age < 18:
            category = "minor"
            allowed_actions = ["read", "comment"]
        elif user_type == "premium":
            category = "premium_adult"
            allowed_actions = ["read", "comment", "post", "moderate"]
        else:
            category = "standard_adult"
            allowed_actions = ["read", "comment", "post"]
        
        {
            "user_category": category,
            "allowed_actions": allowed_actions,
            "access_level": len(allowed_actions)
        }
  input: ["user_age", "user_type"]
  output: ["user_category", "allowed_actions", "access_level"]
  structured_output: true
```

### Error Handling

The Code Node includes comprehensive error handling:

#### Execution Errors

```python
try:
    # Your code here
    result = risky_operation()
    {"result": result}
except Exception as e:
    error": str(e), "status": "failed"}
```

#### Validation Errors

If the code produces invalid output, the node will:
1. Log the error
2. Return an error message in the pipeline
3. Continue execution with appropriate error state

### Performance Considerations

#### Caching

The Code Node uses Pyodide caching for improved performance:
- Package installations are cached
- WebAssembly modules are cached
- Repeated executions are faster

#### Stateless Execution

By default, the Code Node runs in stateless mode for better performance:
- Each execution starts fresh
- No session state is maintained between calls
- Faster initialization

#### Memory Management

- State is serialized/deserialized for security
- Large objects should be handled carefully
- Messages are excluded from state injection to avoid serialization issues

### Dependencies

#### Required

- `langchain-sandbox`: Provides the Pyodide sandbox environment
- `Deno`: JavaScript runtime required by langchain-sandbox

#### Installation

```bash
# Install langchain-sandbox
pip install langchain-sandbox

# Install Deno (if not already installed)
curl -fsSL https://deno.land/install.sh | sh
```

#### Performance Optimization

For optimal performance, run the bootstrap script to enable local caching:

```bash
# Run from the SDK root directory
./scripts/bootstrap.sh
```

This sets up:
- Local package caching
- Optimized Pyodide configuration
- Reduced initialization time

### Integration with Pipeline Flow

#### Sequential Execution

```yaml
nodes:
  - id: "data_input"
    type: "llm"
    # ... configuration
    transition: "process_data"
    
  - id: "process_data"
    type: "code"
    code: 
      type: fixed
      value: |
          # Process the data from previous node
          data = alita_state.get('extracted_data', [])
          processed = [item.upper() for item in data]
          {"processed_items": processed}
    output: ["processed_items"]
    structured_output: true
    transition: "final_output"
    
  - id: "final_output"
    type: "llm"
    # ... configuration
```

### Best Practices

1. **Keep Code Focused**: Each Code Node should have a single, clear purpose
2. **Handle Errors**: Always include error handling in your code
3. **Use Structured Output**: Enable structured output for better state management
4. **Optimize Performance**: Avoid heavy computations in frequently called nodes
5. **Security First**: Never trust external input without validation
6. **State Management**: Be mindful of state variable types and sizes
7. **Documentation**: Comment complex logic within your code blocks

### Troubleshooting

#### Common Issues

**Deno Not Found**
```
Error: Deno is required for PyodideSandbox but is not installed
```
Solution: Install Deno and ensure it's in your PATH

**Serialization Errors**
```
Error: Object is not serializable
```
Solution: Ensure returned objects are JSON-serializable

**Package Import Errors**
```
ModuleNotFoundError: No module named 'package'
```
Solution (depends on lib, has its own limitations): Install packages within the code block:
```python
import micropip
await micropip.install('package-name')
import package
```