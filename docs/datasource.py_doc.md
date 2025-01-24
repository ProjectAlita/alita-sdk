# datasource.py

**Path:** `src/alita_sdk/tools/datasource.py`

## Data Flow

The data flow within `datasource.py` revolves around the handling of queries and responses through the `DatasourcePredict` and `DatasourceSearch` classes. Data originates from the input arguments passed to the `_run` methods of these classes. The `get_query` function extracts the query from the arguments, which is then processed by the respective datasource's `predict` or `search` method. The result is formatted into a response string, which is further processed by the `process_response` function to match the specified return type.

Example:
```python
result = self.datasource.predict(get_query(args, kwargs))
response = f"Response: {result.content}\n\nReferences: {result.additional_kwargs['references']}"
return process_response(response, self.return_type)
```
In this snippet, the query is extracted, processed by the datasource, and the response is formatted and returned.

## Functions Descriptions

### `get_query(args, kwargs)`
This function extracts the query from the provided arguments. If the query is a list, it takes the last element's content.

### `process_response(response, return_type)`
This function formats the response based on the specified return type. If the return type is a string, it returns the response as is; otherwise, it wraps the response in a dictionary.

### `DatasourcePredict`
A class that handles prediction queries. It uses the `predict` method of the datasource to process the query and formats the response.

### `DatasourceSearch`
A class that handles search queries. It uses the `search` method of the datasource to process the query and formats the response.

## Dependencies Used and Their Descriptions

- `Any`, `Type`, `Dict` from `typing`: Used for type annotations.
- `BaseTool` from `langchain_core.tools`: The base class for creating tools.
- `create_model`, `field_validator`, `BaseModel`, `ValidationInfo` from `pydantic`: Used for creating and validating data models.
- `FieldInfo` from `pydantic.fields`: Provides metadata for model fields.
- `clean_string` from `..utils.utils`: A utility function to clean strings.

## Functional Flow

1. **Initialization**: The `DatasourcePredict` and `DatasourceSearch` classes are initialized with the necessary attributes.
2. **Query Extraction**: The `get_query` function extracts the query from the input arguments.
3. **Query Processing**: The query is processed by the datasource's `predict` or `search` method.
4. **Response Formatting**: The result is formatted into a response string and processed by the `process_response` function.
5. **Return Response**: The formatted response is returned.

## Endpoints Used/Created

There are no explicit endpoints defined or used within this file. The functionality is focused on processing queries and responses through the datasource's methods.
