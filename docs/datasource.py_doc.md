# datasource.py

**Path:** `src/alita_sdk/toolkits/datasource.py`

## Data Flow

The data flow within `datasource.py` revolves around the creation and management of tools for interacting with data sources. The primary data elements include client objects, datasource IDs, and selected tools. The data originates from the parameters passed to the `get_toolkit` method, which include a client object, a list of datasource IDs, and an optional list of selected tools. These parameters are used to create instances of `DatasourcePredict` and `DatasourceSearch` tools, which are then stored in the `tools` attribute of the `DatasourcesToolkit` class.

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
In this example, the `get_toolkit` method processes the input parameters to create tool instances, which are then stored in the `tools` list.

## Functions Descriptions

### `toolkit_config_schema`

This static method returns a Pydantic model that defines the schema for the toolkit configuration. It includes fields for the client object, a list of datasource IDs, and a list of selected tools. The client object is required, while the other fields have default values.

### `get_toolkit`

This class method creates and returns an instance of `DatasourcesToolkit` with the specified tools. It takes three parameters: a client object, a list of datasource IDs, and an optional list of selected tools. The method iterates over the datasource IDs, retrieves the corresponding datasource from the client, and creates instances of `DatasourcePredict` and `DatasourceSearch` tools based on the selected tools.

### `get_tools`

This instance method returns the list of tools stored in the `tools` attribute of the `DatasourcesToolkit` instance.

## Dependencies Used and Their Descriptions

### `pydantic`

Pydantic is used for data validation and settings management. In this file, it is used to create a model for the toolkit configuration schema.

### `langchain_community.agent_toolkits.base`

This module provides the `BaseToolkit` class, which is extended by the `DatasourcesToolkit` class.

### `langchain_core.tools`

This module provides the `BaseTool` class, which is used as the base class for the tools created in this file.

### `..tools.datasource`

This module provides the `DatasourcePredict`, `DatasourceSearch`, and `datasourceToolSchema` classes, which are used to create instances of tools for interacting with data sources.

## Functional Flow

1. The `toolkit_config_schema` method defines the schema for the toolkit configuration.
2. The `get_toolkit` method is called with the client object, datasource IDs, and selected tools.
3. The method iterates over the datasource IDs and retrieves the corresponding datasource from the client.
4. Instances of `DatasourcePredict` and `DatasourceSearch` tools are created based on the selected tools.
5. The created tools are stored in the `tools` attribute of the `DatasourcesToolkit` instance.
6. The `get_tools` method returns the list of tools stored in the `tools` attribute.

## Endpoints Used/Created

No explicit endpoints are defined or called within this file.