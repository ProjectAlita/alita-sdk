# datasource.py

**Path:** `src/alita_sdk/toolkits/datasource.py`

## Data Flow

The data flow within `datasource.py` revolves around the creation and management of tools for interacting with various data sources. The primary data elements are the `client`, `datasource_ids`, and `selected_tools`, which are passed as parameters to the `get_toolkit` method. The `client` object is used to fetch data sources based on the provided `datasource_ids`. These data sources are then used to create instances of `DatasourcePredict` and `DatasourceSearch` tools, which are appended to the `tools` list. The data flow can be summarized as follows:

1. **Input Parameters:** The method `get_toolkit` receives `client`, `datasource_ids`, and `selected_tools` as inputs.
2. **Data Source Retrieval:** For each `datasource_id`, the corresponding data source is fetched using the `client` object.
3. **Tool Creation:** Based on the `selected_tools` list, instances of `DatasourcePredict` and `DatasourceSearch` are created and configured with the fetched data source.
4. **Tool Storage:** The created tools are stored in the `tools` list, which is then returned as part of the `DatasourcesToolkit` instance.

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

This static method returns a Pydantic `BaseModel` that defines the schema for the toolkit configuration. The schema includes fields for `datasource_ids` and `selected_tools`, which are lists of data source IDs and selected tool names, respectively. The `datasource_ids` field is required, while the `selected_tools` field has a default value of `['chat', 'search']`.

### `get_toolkit`

This class method is responsible for creating an instance of `DatasourcesToolkit` with the specified tools. It takes three parameters: `client`, `datasource_ids`, and `selected_tools`. The method iterates over the `datasource_ids`, retrieves the corresponding data source using the `client` object, and creates instances of `DatasourcePredict` and `DatasourceSearch` based on the `selected_tools` list. The created tools are stored in the `tools` list, which is then used to instantiate and return a `DatasourcesToolkit` object.

### `get_tools`

This instance method returns the list of tools stored in the `tools` attribute of the `DatasourcesToolkit` instance. It provides access to the tools created and configured by the `get_toolkit` method.

## Dependencies Used and Their Descriptions

### `pydantic`

The `pydantic` library is used to create and manage data models. In this file, it is used to define the schema for the toolkit configuration using the `create_model` function and the `BaseModel` class.

### `langchain_community.agent_toolkits.base`

This module provides the `BaseToolkit` class, which is the base class for the `DatasourcesToolkit` class defined in this file. It provides common functionality for toolkits in the LangChain community.

### `langchain_core.tools`

This module provides the `BaseTool` class, which is the base class for the tools created and managed by the `DatasourcesToolkit` class. It provides common functionality for tools in the LangChain core library.

### `DatasourcePredict` and `DatasourceSearch`

These classes are imported from the `..tools.datasource` module and are used to create instances of tools for predicting and searching data sources, respectively. They are configured with the fetched data source and added to the `tools` list in the `get_toolkit` method.

## Functional Flow

The functional flow of `datasource.py` involves the following steps:

1. **Toolkit Configuration Schema:** The `toolkit_config_schema` method defines the schema for the toolkit configuration.
2. **Toolkit Creation:** The `get_toolkit` method is called with the `client`, `datasource_ids`, and `selected_tools` parameters. It retrieves the data sources, creates the tools, and returns a `DatasourcesToolkit` instance.
3. **Tool Access:** The `get_tools` method is called on the `DatasourcesToolkit` instance to access the created tools.

Example:
```python
toolkit = DatasourcesToolkit.get_toolkit(client, datasource_ids, selected_tools)
tools = toolkit.get_tools()
```

## Endpoints Used/Created

There are no explicit endpoints defined or used within `datasource.py`. The file focuses on creating and managing tools for interacting with data sources, which are configured and used within the LangChain framework.