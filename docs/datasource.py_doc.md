# datasource.py

**Path:** `src/alita_sdk/tools/datasource.py`

## Data Flow

The data flow within `datasource.py` revolves around the interaction between the user inputs, the datasource, and the processing of responses. The primary data elements are the search query and the responses from the datasource. The query is initially received as an argument or keyword argument in the functions `get_query` and `_run`. The `get_query` function extracts the query from the arguments, handling cases where the query might be a list of messages. This query is then passed to the datasource's `predict` or `search` methods, depending on the class being used (`DatasourcePredict` or `DatasourceSearch`). The response from the datasource is processed by the `process_response` function, which formats it based on the specified return type. The final output is either a string or a dictionary containing the response messages.

Example:
```python
# Extracting the query from arguments
query = kwargs.get('query', kwargs.get('messages'))
if isinstance(query, list):
    query = query[-1].content
```
This snippet shows how the query is extracted from the arguments, handling cases where it might be a list of messages.

## Functions Descriptions

### get_query

This function extracts the search query from the provided arguments. It checks if the query is passed as a positional argument or a keyword argument. If the query is a list, it extracts the content of the last message.

**Inputs:**
- `args`: Positional arguments
- `kwargs`: Keyword arguments

**Outputs:**
- `query`: The extracted search query

### process_response

This function processes the response from the datasource based on the specified return type. It formats the response as a string or a dictionary containing the response messages.

**Inputs:**
- `response`: The response from the datasource
- `return_type`: The desired return type (string or dictionary)

**Outputs:**
- Formatted response

### DatasourcePredict

This class represents a tool for making predictions using a datasource. It defines the schema for the input arguments and the return type. The `_run` method executes the prediction and processes the response.

**Inputs:**
- `args`: Positional arguments
- `kwargs`: Keyword arguments

**Outputs:**
- Processed response

### DatasourceSearch

This class represents a tool for searching using a datasource. Similar to `DatasourcePredict`, it defines the schema for the input arguments and the return type. The `_run` method executes the search and processes the response.

**Inputs:**
- `args`: Positional arguments
- `kwargs`: Keyword arguments

**Outputs:**
- Processed response

## Dependencies Used and Their Descriptions

### Any, Type, Dict (from typing)

These are type hints used to specify the expected types of variables and function parameters.

### BaseTool (from langchain_core.tools)

This is the base class for creating tools in the LangChain framework. `DatasourcePredict` and `DatasourceSearch` inherit from this class.

### create_model, field_validator, BaseModel, ValidationInfo, FieldInfo (from pydantic)

These are utilities from the Pydantic library used for creating and validating data models. They are used to define the schema for the input arguments of the tools.

### clean_string (from ..utils.utils)

This is a utility function for cleaning strings, used in the `remove_spaces_name` method of `DatasourceSearch`.

## Functional Flow

1. The user provides a search query as an argument or keyword argument.
2. The `get_query` function extracts the query from the arguments.
3. The query is passed to the datasource's `predict` or `search` method.
4. The datasource processes the query and returns a response.
5. The `process_response` function formats the response based on the specified return type.
6. The formatted response is returned to the user.

## Endpoints Used/Created

There are no explicit endpoints defined or used within this file. The interaction with the datasource is abstracted through the `predict` and `search` methods of the datasource object.