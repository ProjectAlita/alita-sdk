# vectorstore.py

**Path:** `src/alita_sdk/toolkits/vectorstore.py`

## Data Flow

The data flow within `vectorstore.py` revolves around the configuration and utilization of vector stores for embedding models. The data originates from the parameters provided to the `get_toolkit` method, which include the language model (`llm`), vector store type, embedding model, and their respective parameters. These inputs are used to initialize a `VectorStoreWrapper` object, which manages the interaction with the vector store. The selected tools are then filtered and instantiated as `BaseAction` objects, which are stored in the `tools` attribute of the `VectorStoreToolkit` class. The data flow can be summarized as follows:

1. **Input Parameters:** The method `get_toolkit` receives input parameters such as `llm`, `vectorstore_type`, `embedding_model`, `embedding_model_params`, and `vectorstore_params`.
2. **VectorStoreWrapper Initialization:** These parameters are used to initialize a `VectorStoreWrapper` object, which handles the connection and interaction with the vector store.
3. **Tool Selection:** The available tools from the `VectorStoreWrapper` are filtered based on the `selected_tools` parameter.
4. **Tool Instantiation:** The selected tools are instantiated as `BaseAction` objects and stored in the `tools` attribute of the `VectorStoreToolkit` class.

Example:
```python
vectorstore_wrapper = VectorStoreWrapper(llm=llm,
                                         vectorstore_type=vectorstore_type,
                                         embedding_model=embedding_model, 
                                         embedding_model_params=embedding_model_params, 
                                         vectorstore_params=vectorstore_params)
available_tools = vectorstore_wrapper.get_available_tools()
```

## Functions Descriptions

### `toolkit_config_schema`

This static method returns a Pydantic `BaseModel` that defines the configuration schema for the toolkit. It dynamically creates a model based on the available tools from the `VectorStoreWrapper`.

- **Inputs:** None
- **Outputs:** A Pydantic `BaseModel` representing the configuration schema.

### `get_toolkit`

This class method initializes the `VectorStoreWrapper` with the provided parameters and filters the available tools based on the `selected_tools` parameter. It returns an instance of `VectorStoreToolkit` with the selected tools.

- **Inputs:**
  - `llm`: The language model to be used.
  - `vectorstore_type`: The type of vector store (e.g., Chroma, PGVector, Elastic).
  - `embedding_model`: The embedding model to be used.
  - `embedding_model_params`: Parameters for the embedding model.
  - `vectorstore_params`: Connection parameters for the vector store.
  - `selected_tools`: A list of selected tools (optional).
- **Outputs:** An instance of `VectorStoreToolkit` with the selected tools.

### `get_tools`

This method returns the list of tools stored in the `tools` attribute of the `VectorStoreToolkit` instance.

- **Inputs:** None
- **Outputs:** A list of `BaseTool` objects.

## Dependencies Used and Their Descriptions

### `logging`

- **Purpose:** Used for logging information and debugging messages.
- **Usage:** The `getLogger` function is used to create a logger instance for the module.

### `typing`

- **Purpose:** Provides type hints for function signatures and variable declarations.
- **Usage:** The `Any`, `List`, and `Literal` types are used for type annotations.

### `pydantic`

- **Purpose:** Used for data validation and settings management using Python type annotations.
- **Usage:** The `BaseModel`, `create_model`, and `Field` classes are used to define the configuration schema for the toolkit.

### `langchain_core.tools`

- **Purpose:** Provides base classes for toolkits and tools.
- **Usage:** The `BaseToolkit` and `BaseTool` classes are extended to create the `VectorStoreToolkit` class.

### `alita_tools.base.tool`

- **Purpose:** Provides base classes for actions.
- **Usage:** The `BaseAction` class is used to create action objects for the selected tools.

### `..tools.vectorstore`

- **Purpose:** Provides the `VectorStoreWrapper` class, which manages the interaction with the vector store.
- **Usage:** The `VectorStoreWrapper` class is instantiated and used to get the available tools.

## Functional Flow

The functional flow of `vectorstore.py` involves the following steps:

1. **Configuration Schema Definition:** The `toolkit_config_schema` method defines the configuration schema for the toolkit based on the available tools from the `VectorStoreWrapper`.
2. **Toolkit Initialization:** The `get_toolkit` method initializes the `VectorStoreWrapper` with the provided parameters and filters the available tools based on the `selected_tools` parameter.
3. **Tool Instantiation:** The selected tools are instantiated as `BaseAction` objects and stored in the `tools` attribute of the `VectorStoreToolkit` class.
4. **Tool Retrieval:** The `get_tools` method returns the list of tools stored in the `tools` attribute.

Example:
```python
tools = []
vectorstore_wrapper = VectorStoreWrapper(llm=llm,
                                         vectorstore_type=vectorstore_type,
                                         embedding_model=embedding_model, 
                                         embedding_model_params=embedding_model_params, 
                                         vectorstore_params=vectorstore_params)
available_tools = vectorstore_wrapper.get_available_tools()
for tool in available_tools:
    tools.append(BaseAction(
        api_wrapper=vectorstore_wrapper,
        name=tool["name"],
        description=tool["description"],
        args_schema=tool["args_schema"]
    ))
return cls(tools=tools)
```

## Endpoints Used/Created

There are no explicit endpoints used or created in `vectorstore.py`. The functionality is focused on configuring and utilizing vector stores for embedding models within the context of a toolkit.