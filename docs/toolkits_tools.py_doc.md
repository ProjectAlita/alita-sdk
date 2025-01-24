# tools.py

**Path:** `src/alita_sdk/toolkits/tools.py`

## Data Flow

The data flow within `tools.py` is centered around the `get_toolkits` and `get_tools` functions. The `get_toolkits` function returns a list of toolkit configuration schemas, which are essentially the configurations for different toolkits like `PromptToolkit`, `DatasourcesToolkit`, `ApplicationToolkit`, and `ArtifactToolkit`. These configurations are then used by the `get_tools` function to generate a list of tools based on the provided `tools_list` and an instance of `AlitaClient`.

In the `get_tools` function, the data flow starts with an empty list of `prompts` and `tools`. The function iterates over each tool in the `tools_list`, categorizing them by their type (`prompt`, `datasource`, `application`, or `artifact`). Depending on the type, it either appends to the `prompts` list or extends the `tools` list with tools fetched from the respective toolkit. Finally, if there are any prompts, it fetches tools from the `PromptToolkit` and combines them with the tools fetched from the `alita_tools` function.

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
    elif tool['type'] == 'datasource':
        tools.extend(DatasourcesToolkit.get_toolkit(
            alita,
            datasource_ids=[int(tool['settings']['datasource_id'])],
            selected_tools=tool['settings']['selected_tools']).get_tools())
    # Additional conditions for other tool types
```

## Functions Descriptions

### `get_toolkits`

This function returns a list of toolkit configuration schemas. It does not take any parameters and simply returns the configuration schemas for `PromptToolkit`, `DatasourcesToolkit`, `ApplicationToolkit`, and `ArtifactToolkit`.

Example:
```python
def get_toolkits():
    return [
        PromptToolkit.toolkit_config_schema(),
        DatasourcesToolkit.toolkit_config_schema(),
        ApplicationToolkit.toolkit_config_schema(),
        ArtifactToolkit.toolkit_config_schema()
    ]
```

### `get_tools`

This function generates a list of tools based on the provided `tools_list` and an instance of `AlitaClient`. It categorizes the tools by their type and fetches the appropriate tools from the respective toolkits. It handles different tool types like `prompt`, `datasource`, `application`, and `artifact`.

Example:
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

### `logging`

The `logging` module is used to create a logger for the file. This logger can be used to log messages for debugging and monitoring purposes.

### `alita_tools`

The `alita_tools` function is imported from the `alita_tools` module. It is used in the `get_tools` function to fetch additional tools based on the `tools_list`.

### `PromptToolkit`, `DatasourcesToolkit`, `ApplicationToolkit`, `ArtifactToolkit`

These are imported from their respective modules and are used to fetch toolkit configuration schemas and tools based on the type of tool specified in the `tools_list`.

## Functional Flow

1. The `get_toolkits` function is called to fetch the configuration schemas for different toolkits.
2. The `get_tools` function is called with a `tools_list` and an instance of `AlitaClient`.
3. Inside `get_tools`, the function iterates over each tool in the `tools_list` and categorizes them by their type.
4. Depending on the type, it fetches the appropriate tools from the respective toolkits and appends or extends the `tools` list.
5. If there are any prompts, it fetches tools from the `PromptToolkit` and combines them with the tools fetched from the `alita_tools` function.
6. The final list of tools is returned.

## Endpoints Used/Created

No explicit endpoints are defined or called within this file.