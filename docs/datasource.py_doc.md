# datasource.py

**Path:** `src/alita_sdk/toolkits/datasource.py`

## Data Flow

The data flow within the `datasource.py` file revolves around the creation and management of tools that interact with data sources. The primary class, `DatasourcesToolkit`, is responsible for configuring and providing these tools based on the provided client and data source IDs. The data flow can be summarized as follows:

1. **Input Data:** The input data includes a client object, a list of data source IDs, and an optional list of selected tools.
2. **Data Transformation:** The `get_toolkit` class method processes the input data to create instances of `DatasourcePredict` and `DatasourceSearch` tools for each data source ID. These tools are configured with the appropriate data source and schema.
3. **Output Data:** The output is a `DatasourcesToolkit` instance containing the configured tools.

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
In this example, the `get_toolkit` method processes the input data (client, data source IDs, and selected tools) to create and configure the appropriate tools.

## Functions Descriptions

### `toolkit_config_schema`

This static method returns a Pydantic `BaseModel` that defines the schema for configuring the toolkit. The schema includes fields for the client object, a list of data source IDs, and a list of selected tools.

### `get_toolkit`

This class method creates and configures tools based on the provided client, data source IDs, and selected tools. It iterates over the data source IDs, retrieves the corresponding data source from the client, and creates instances of `DatasourcePredict` and `DatasourceSearch` tools as needed.

### `get_tools`

This instance method returns the list of tools contained within the `DatasourcesToolkit` instance.

## Dependencies Used and Their Descriptions

### `List` and `Any` from `typing`

These are used for type hinting to specify the expected types of variables and function parameters.

### `create_model` and `BaseModel` from `pydantic`

These are used to create and define data models for validating and parsing input data.

### `FieldInfo` from `pydantic.fields`

This is used to provide additional metadata for fields in the Pydantic models, such as descriptions and default values.

### `BaseToolkit` from `langchain_community.agent_toolkits.base`

This is the base class for creating toolkits in the LangChain community.

### `BaseTool` from `langchain_core.tools`

This is the base class for creating individual tools in the LangChain core library.

### `DatasourcePredict`, `DatasourceSearch`, and `datasourceToolSchema` from `..tools.datasource`

These are specific tools and schemas used for interacting with data sources.

## Functional Flow

The functional flow of the `datasource.py` file involves the following steps:

1. **Toolkit Configuration:** The `toolkit_config_schema` method defines the schema for configuring the toolkit.
2. **Toolkit Creation:** The `get_toolkit` method creates and configures tools based on the provided client, data source IDs, and selected tools.
3. **Tool Retrieval:** The `get_tools` method returns the list of tools contained within the `DatasourcesToolkit` instance.

Example:
```python
toolkit = DatasourcesToolkit.get_toolkit(client, datasource_ids, selected_tools)
tools = toolkit.get_tools()
```
In this example, the `get_toolkit` method is used to create a `DatasourcesToolkit` instance, and the `get_tools` method is used to retrieve the configured tools.

## Endpoints Used/Created

The `datasource.py` file does not explicitly define or call any endpoints. Instead, it focuses on creating and configuring tools for interacting with data sources. The actual interaction with data sources is handled by the `DatasourcePredict` and `DatasourceSearch` tools, which are configured with the appropriate data source and schema.