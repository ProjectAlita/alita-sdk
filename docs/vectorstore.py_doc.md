# vectorstore.py

**Path:** `src/alita_sdk/toolkits/vectorstore.py`

## Data Flow

The data flow within `vectorstore.py` revolves around the configuration and utilization of vector stores for embedding models. The data originates from the parameters provided to the `get_toolkit` method, which include the language model (`llm`), vector store type, embedding model, and their respective parameters. These inputs are used to initialize a `VectorStoreWrapper` object, which manages the interaction with the vector store. The `get_toolkit` method also processes a list of selected tools, which are filtered and instantiated as `BaseAction` objects. These tools are then stored in the `tools` attribute of the `VectorStoreToolkit` class. The data flow can be summarized as follows:

1. Input parameters are received by the `get_toolkit` method.
2. A `VectorStoreWrapper` object is initialized with these parameters.
3. Available tools are retrieved from the `VectorStoreWrapper`.
4. Selected tools are filtered and instantiated as `BaseAction` objects.
5. The instantiated tools are stored in the `tools` attribute.

Example:
```python
vectorstore_wrapper = VectorStoreWrapper(llm=llm,
                                         vectorstore_type=vectorstore_type,
                                         embedding_model=embedding_model, 
                                         embedding_model_params=embedding_model_params, 
                                         vectorstore_params=vectorstore_params)
available_tools = vectorstore_wrapper.get_available_tools()
```
In this example, the `VectorStoreWrapper` is initialized with the provided parameters, and the available tools are retrieved for further processing.

## Functions Descriptions

### `toolkit_config_schema`

This static method generates a configuration schema for the toolkit using Pydantic's `create_model` function. It retrieves available tools from the `VectorStoreWrapper` and constructs a dynamic model with fields for embedding model, vector store type, and selected tools.

### `get_toolkit`

This class method initializes a `VectorStoreWrapper` with the provided parameters and retrieves available tools. It filters the tools based on the `selected_tools` list and instantiates them as `BaseAction` objects. The method returns an instance of `VectorStoreToolkit` with the instantiated tools.

### `get_tools`

This method returns the list of tools stored in the `tools` attribute of the `VectorStoreToolkit` instance.

## Dependencies Used and Their Descriptions

- `logging`: Used for logging information and debugging messages.
- `typing`: Provides type hints for function signatures and variable declarations.
- `pydantic`: Used for creating dynamic models and validating data.
- `langchain_core.tools`: Provides base classes for toolkits and tools.
- `alita_tools.base.tool`: Provides the `BaseAction` class for defining actions.
- `..tools.vectorstore`: Imports the `VectorStoreWrapper` class for managing vector store interactions.

## Functional Flow

1. The `VectorStoreToolkit` class is defined with a `tools` attribute.
2. The `toolkit_config_schema` method generates a configuration schema for the toolkit.
3. The `get_toolkit` method initializes a `VectorStoreWrapper` and retrieves available tools.
4. Selected tools are filtered and instantiated as `BaseAction` objects.
5. The `get_tools` method returns the list of instantiated tools.

## Endpoints Used/Created

No explicit endpoints are defined or used within this file. The functionality is focused on configuring and managing vector store interactions through the `VectorStoreWrapper` class.