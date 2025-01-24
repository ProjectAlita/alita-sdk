# tools.py

**Path:** `src/alita_sdk/toolkits/tools.py`

## Data Flow

The data flow within `tools.py` is centered around the retrieval and configuration of various toolkits and tools based on the provided input. The primary functions, `get_toolkits` and `get_tools`, orchestrate this process. The `get_toolkits` function returns a list of toolkit configuration schemas, while the `get_tools` function processes a list of tools, categorizing them by type and retrieving the appropriate toolkit configurations and tools. Data originates from the input parameters, undergoes transformations based on the type of tool, and is ultimately returned as a list of configured tools. Intermediate variables such as `prompts` and `tools` are used to temporarily store data during processing.

Example:
```python
prompts = []
tools = []
for tool in tools_list:
    if tool['type'] == 'prompt':
        prompts.append([
            int(tool['settings']['prompt_id']),
            int(tool['settings']['prompt_version_id'])
        ])
    # Additional processing for other tool types
```
This snippet shows the initial categorization of tools into prompts and other types, with data being temporarily stored in the `prompts` and `tools` lists.

## Functions Descriptions

### get_toolkits

This function returns a list of toolkit configuration schemas. It does not take any parameters and simply aggregates the configuration schemas from various toolkits.

```python
def get_toolkits():
    return [
        PromptToolkit.toolkit_config_schema(),
        DatasourcesToolkit.toolkit_config_schema(),
        ApplicationToolkit.toolkit_config_schema(),
        ArtifactToolkit.toolkit_config_schema()
    ]
```

### get_tools

This function processes a list of tools and retrieves the appropriate toolkit configurations and tools based on the type of each tool. It takes two parameters: `tools_list`, a list of tools to be processed, and `alita`, an instance of `AlitaClient`.

```python
def get_tools(tools_list: list, alita: 'AlitaClient') -> list:
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
        elif tool['type'] == 'application':
            tools.extend(ApplicationToolkit.get_toolkit(
                alita,
                application_id=int(tool['settings']['application_id']),
                application_version_id=int(tool['settings']['application_version_id']),
                app_api_key=alita.auth_token,
                selected_tools=[]
            ).get_tools())
        elif tool['type'] == 'artifact':
            tools.extend(ArtifactToolkit.get_toolkit(
                client=alita,
                bucket=tool['settings']['bucket'],
                selected_tools=tool['settings'].get('selected_tools', [])
            ).get_tools())
    if len(prompts) > 0:
        tools += PromptToolkit.get_toolkit(alita, prompts).get_tools()
    tools += alita_tools(tools_list)
    return tools
```

## Dependencies Used and Their Descriptions

### logging

The `logging` module is used to create a logger instance for the file. This logger can be used to log messages for debugging and monitoring purposes.

### alita_tools

The `alita_tools` function is imported from the `alita_tools` module. It is used in the `get_tools` function to retrieve additional tools based on the provided `tools_list`.

### PromptToolkit, DatasourcesToolkit, ApplicationToolkit, ArtifactToolkit

These modules are imported from the same package and are used to retrieve toolkit configuration schemas and tools based on the type of tool being processed.

## Functional Flow

The functional flow of `tools.py` begins with the `get_toolkits` function, which aggregates and returns a list of toolkit configuration schemas. The `get_tools` function then processes a list of tools, categorizing them by type and retrieving the appropriate toolkit configurations and tools. The flow involves iterating over the list of tools, categorizing them, and retrieving the necessary configurations and tools based on their type. The final list of tools is then returned.

## Endpoints Used/Created

There are no explicit endpoints used or created in `tools.py`. The file primarily focuses on retrieving and configuring toolkits and tools based on the provided input.