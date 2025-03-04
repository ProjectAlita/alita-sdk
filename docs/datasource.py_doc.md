# datasource.py

**Path:** `src/alita_sdk/toolkits/datasource.py`

## Data Flow

The data flow within `datasource.py` revolves around the creation and management of tools for interacting with various data sources. The data originates from the client object and the list of datasource IDs provided as input parameters. These inputs are used to instantiate specific tools (`DatasourcePredict` and `DatasourceSearch`) based on the selected tools specified. The data is then transformed into tool objects, which are stored in the `tools` attribute of the `DatasourcesToolkit` class. The final destination of the data is the list of tools that can be retrieved using the `get_tools` method.

Example:
```python
@classmethod
 def get_toolkit(cls, client: Any, datasource_ids: list[int], selected_tools: list[str] = []):
 tools = []
 for datasource_id in datasource_ids:
 datasource = client.datasource(datasource_id)
 if len(selected_tools) == 0 or 'chat' in selected_tools:
 tools.append(DatasourcePredict(name=f'{datasource.name}Predict', 
 description=f'Search and summarize. {datasource.description}',
 datasource=datasource, 
 args_schema=datasourceToolSchema,
 return_type='str'))
 if len(selected_tools) == 0 or 'search' in selected_tools:
 tools.append(DatasourceSearch(name=f'{datasource.name}Search', 
 description=f'Search return results. {datasource.description}',
 datasource=datasource, 
 args_schema=datasourceToolSchema,
 return_type='str'))
 return cls(tools=tools)
```

## Functions Descriptions

### `toolkit_config_schema`

This static method returns a Pydantic model that defines the schema for the toolkit configuration. It includes fields for `datasource_ids` and `selected_tools`, which are lists of datasource IDs and selected tools, respectively.

### `get_toolkit`

This class method creates and returns an instance of `DatasourcesToolkit` with the specified tools. It takes three parameters: `client`, `datasource_ids`, and `selected_tools`. The method iterates over the datasource IDs, retrieves the corresponding datasource object from the client, and appends the appropriate tools to the `tools` list based on the selected tools.

### `get_tools`

This method returns the list of tools stored in the `tools` attribute of the `DatasourcesToolkit` instance.

## Dependencies Used and Their Descriptions

### `pydantic`

Used for creating and validating data models. The `create_model` function is used to dynamically create a Pydantic model for the toolkit configuration schema.

### `langchain_community.agent_toolkits.base`

Provides the `BaseToolkit` class, which `DatasourcesToolkit` inherits from.

### `langchain_core.tools`

Provides the `BaseTool` class, which is the base class for the tools used in the toolkit.

### `..tools.datasource`

Imports the `DatasourcePredict`, `DatasourceSearch`, and `datasourceToolSchema` components, which are used to create the tools for the toolkit.

## Functional Flow

1. The `toolkit_config_schema` method is called to define the configuration schema for the toolkit.
2. The `get_toolkit` method is called with the client, datasource IDs, and selected tools as parameters.
3. The method iterates over the datasource IDs and retrieves the corresponding datasource object from the client.
4. Based on the selected tools, the method creates instances of `DatasourcePredict` and `DatasourceSearch` and appends them to the `tools` list.
5. The `get_tools` method can be called to retrieve the list of tools created.

## Endpoints Used/Created

No explicit endpoints are defined or used within this file.