# tools.py

**Path:** `src/alita_sdk/toolkits/tools.py`

## Data Flow

The data flow within `tools.py` is centered around the retrieval and configuration of various toolkits and tools. The primary functions, `get_toolkits` and `get_tools`, orchestrate the flow of data by aggregating configurations and tool instances from different sources. The data originates from predefined configurations and user inputs, which are then processed and transformed into toolkit schemas and tool instances. The data is temporarily stored in lists such as `core_toolkits`, `community_toolkits`, `prompts`, and `tools`. These lists are then combined and returned as the final output. The direction of data movement is from configuration definitions to toolkit and tool instances, which are then utilized by the Alita client and LLM objects.

Example:
```python
core_toolkits = [
    PromptToolkit.toolkit_config_schema(),
    DatasourcesToolkit.toolkit_config_schema(),
    ApplicationToolkit.toolkit_config_schema(),
    ArtifactToolkit.toolkit_config_schema(),
    VectorStoreToolkit.toolkit_config_schema()
]
```
In this snippet, the `core_toolkits` list is populated with configuration schemas from various toolkits, demonstrating the initial stage of data aggregation.

## Functions Descriptions

### get_toolkits

The `get_toolkits` function is responsible for aggregating and returning a list of toolkit configuration schemas. It combines core toolkits and community toolkits with additional toolkits retrieved from the `alita_toolkits` function.

- **Inputs:** None
- **Processing Logic:** Aggregates toolkit configuration schemas from core and community toolkits.
- **Outputs:** A combined list of toolkit configuration schemas.

Example:
```python
def get_toolkits():
    core_toolkits = [
        PromptToolkit.toolkit_config_schema(),
        DatasourcesToolkit.toolkit_config_schema(),
        ApplicationToolkit.toolkit_config_schema(),
        ArtifactToolkit.toolkit_config_schema(),
        VectorStoreToolkit.toolkit_config_schema()
    ]
    community_toolkits = [ 
        AnalyseJira.toolkit_config_schema()
    ]
    return core_toolkits + community_toolkits + alita_toolkits()
```

### get_tools

The `get_tools` function retrieves and configures tools based on a provided list of tool definitions. It processes each tool definition, identifies its type, and retrieves the corresponding tools from the appropriate toolkit.

- **Inputs:**
  - `tools_list`: A list of tool definitions.
  - `alita`: An instance of `AlitaClient`.
  - `llm`: An instance of `LLMLikeObject`.
- **Processing Logic:** Iterates through the tool definitions, retrieves tools from the appropriate toolkit, and aggregates them into a final list.
- **Outputs:** A combined list of tool instances.

Example:
```python
def get_tools(tools_list: list, alita: 'AlitaClient', llm: 'LLMLikeObject') -> list:
    prompts = []
    tools = []
    for tool in tools_list:
        if tool['type'] == 'prompt':
            prompts.append([
                int(tool['settings']['prompt_id']),
                int(tool['settings']['prompt_version_id'])
            ])
        elif tool['type'] == 'datasource':
            tools.extend(DatasourcesToolkit.get_toolkit(
                alita,
                datasource_ids=[int(tool['settings']['datasource_id'])],
                selected_tools=tool['settings']['selected_tools']).get_tools())
        # Additional tool types processed similarly...
    if len(prompts) > 0:
        tools += PromptToolkit.get_toolkit(alita, prompts).get_tools()
    tools += alita_tools(tools_list, alita, llm)
    return tools
```

## Dependencies Used and Their Descriptions

### alita_tools and alita_toolkits

These functions are imported from the `alita_tools` module and are used to retrieve additional tools and toolkits. They play a crucial role in extending the functionality by incorporating external tool definitions.

### PromptToolkit, DatasourcesToolkit, ApplicationToolkit, ArtifactToolkit, VectorStoreToolkit

These modules provide the core toolkit configuration schemas and tool retrieval functions. Each toolkit is responsible for a specific domain, such as prompts, data sources, applications, artifacts, and vector stores.

### AnalyseJira

This community toolkit is imported from the `community.eda.jiratookit` module and provides functionality for analyzing Jira data.

### logging

The `logging` module is used to set up a logger for the file, which helps in tracking and debugging the execution flow.

## Functional Flow

The functional flow in `tools.py` begins with the definition of the `get_toolkits` and `get_tools` functions. When these functions are called, they aggregate and configure toolkits and tools based on predefined schemas and user inputs. The sequence of operations involves iterating through tool definitions, identifying their types, and retrieving the corresponding tools from the appropriate toolkits. The final output is a combined list of tool instances that can be utilized by the Alita client and LLM objects.

Example:
```python
def get_tools(tools_list: list, alita: 'AlitaClient', llm: 'LLMLikeObject') -> list:
    prompts = []
    tools = []
    for tool in tools_list:
        if tool['type'] == 'prompt':
            prompts.append([
                int(tool['settings']['prompt_id']),
                int(tool['settings']['prompt_version_id'])
            ])
        elif tool['type'] == 'datasource':
            tools.extend(DatasourcesToolkit.get_toolkit(
                alita,
                datasource_ids=[int(tool['settings']['datasource_id'])],
                selected_tools=tool['settings']['selected_tools']).get_tools())
        # Additional tool types processed similarly...
    if len(prompts) > 0:
        tools += PromptToolkit.get_toolkit(alita, prompts).get_tools()
    tools += alita_tools(tools_list, alita, llm)
    return tools
```

## Endpoints Used/Created

There are no explicit endpoints defined or used within `tools.py`. The file focuses on the configuration and retrieval of toolkits and tools, without directly interacting with external endpoints.