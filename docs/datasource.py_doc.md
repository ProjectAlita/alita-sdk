# datasource.py

**Path:** `src/alita_sdk/tools/datasource.py`

## Data Flow

The data flow within `datasource.py` revolves around the handling of search queries and responses from a datasource. The primary data elements are the search query and the response from the datasource. The query is initially received as an argument or keyword argument in the functions `get_query` and `_run`. The `get_query` function processes the input to extract the query string, which can be a direct string or a list of messages. This query is then passed to the datasource's `predict` or `search` methods, depending on the class (`DatasourcePredict` or `DatasourceSearch`). The response from the datasource is processed and formatted into a string or a dictionary with messages, which is then returned as the final output.

Example:
```python
# Extracting query from arguments
query = kwargs.get('query', kwargs.get('messages'))
if isinstance(query, list):
    query = query[-1].content
```
This snippet shows how the query is extracted from the input arguments, demonstrating the initial step in the data flow.

## Functions Descriptions

### `get_query(args, kwargs)`
This function extracts the search query from the provided arguments. It checks if the query is passed as a positional argument or a keyword argument. If the query is a list, it extracts the content of the last message.

### `process_response(response, return_type)`
This function formats the response from the datasource. If the return type is a string, it returns the response directly. Otherwise, it wraps the response in a dictionary with a messages key.

### `DatasourcePredict`
A class that extends `BaseTool` and is used for making predictions using a datasource. It defines the schema for the arguments and the return type. The `_run` method processes the query and formats the response.

### `DatasourceSearch`
Similar to `DatasourcePredict`, this class is used for searching a datasource. It also extends `BaseTool` and defines the schema for the arguments and the return type. The `_run` method processes the query and formats the search results.

## Dependencies Used and Their Descriptions

### `typing`
Used for type hinting and defining the types of variables and function return values.

### `langchain_core.tools.BaseTool`
A base class for creating tools that interact with datasources.

### `pydantic`
Used for data validation and settings management using Python type annotations. It helps in creating models and validating fields.

### `..utils.utils.clean_string`
A utility function used to clean and format strings.

## Functional Flow

1. **Initialization**: The `DatasourcePredict` and `DatasourceSearch` classes are initialized with the necessary attributes such as name, description, datasource, args_schema, and return_type.
2. **Query Extraction**: The `get_query` function extracts the query from the input arguments.
3. **Prediction/Search**: The `_run` method of the respective class calls the datasource's `predict` or `search` method with the extracted query.
4. **Response Processing**: The response from the datasource is processed and formatted using the `process_response` function.
5. **Return Output**: The formatted response is returned as the final output.

## Endpoints Used/Created

This file does not explicitly define or call any endpoints. The interaction is primarily with the datasource object, which is expected to have `predict` and `search` methods.