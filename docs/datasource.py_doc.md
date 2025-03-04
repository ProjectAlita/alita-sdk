# datasource.py

**Path:** `src/alita_sdk/tools/datasource.py`

## Data Flow

The data flow within `datasource.py` revolves around the handling of search queries and responses from a datasource. The primary data elements are the search query and the response from the datasource. The search query is initially received as an argument or keyword argument in the functions `get_query` and `_run`. The `get_query` function processes the input to extract the query string, which can be a direct string or a list of messages. This query is then passed to the datasource's `predict` or `search` methods, depending on the class being used (`DatasourcePredict` or `DatasourceSearch`). The response from the datasource is processed by the `process_response` function, which formats it based on the specified return type (`str` or a dictionary with messages). The final output is a formatted string or dictionary that includes the response content and any additional references.

Example:
```python
# Extracting query from arguments
query = kwargs.get('query', kwargs.get('messages'))
if isinstance(query, list):
    query = query[-1].content
return query
```
This snippet shows how the `get_query` function extracts the query from the provided arguments, handling both direct strings and lists of messages.

## Functions Descriptions

1. **get_query(args, kwargs):**
   - **Purpose:** Extracts the search query from the provided arguments.
   - **Inputs:** `args` (tuple), `kwargs` (dict)
   - **Processing:** Checks if the query is in `args` or `kwargs`, handles lists of messages.
   - **Outputs:** Returns the query string.

2. **process_response(response, return_type):**
   - **Purpose:** Formats the response based on the return type.
   - **Inputs:** `response` (str), `return_type` (str)
   - **Processing:** Returns the response as a string or a dictionary with messages.
   - **Outputs:** Formatted response.

3. **DatasourcePredict._run(*args, **kwargs):**
   - **Purpose:** Runs the prediction using the datasource.
   - **Inputs:** `args` (tuple), `kwargs` (dict)
   - **Processing:** Extracts the query, calls `datasource.predict`, formats the response.
   - **Outputs:** Formatted prediction response.

4. **DatasourceSearch._run(*args, **kwargs):**
   - **Purpose:** Runs the search using the datasource.
   - **Inputs:** `args` (tuple), `kwargs` (dict)
   - **Processing:** Extracts the query, calls `datasource.search`, formats the response.
   - **Outputs:** Formatted search response.

## Dependencies Used and Their Descriptions

1. **typing:**
   - **Purpose:** Provides type hints for better code readability and maintenance.
   - **Usage:** Used to specify types for variables and function return values.

2. **langchain_core.tools.BaseTool:**
   - **Purpose:** Base class for creating tools in the LangChain framework.
   - **Usage:** `DatasourcePredict` and `DatasourceSearch` classes inherit from `BaseTool`.

3. **pydantic:**
   - **Purpose:** Data validation and settings management using Python type annotations.
   - **Usage:** Used to create models (`datasourceToolSchema`) and validate fields (`field_validator`).

4. **..utils.utils.clean_string:**
   - **Purpose:** Utility function to clean strings.
   - **Usage:** Used in `DatasourceSearch` to clean the `name` field.

## Functional Flow

1. **Initialization:**
   - The `DatasourcePredict` and `DatasourceSearch` classes are initialized with a name, description, datasource, and other parameters.

2. **Query Extraction:**
   - The `get_query` function extracts the search query from the provided arguments.

3. **Prediction/Search Execution:**
   - The `_run` method of `DatasourcePredict` or `DatasourceSearch` is called, which uses the extracted query to call the `predict` or `search` method of the datasource.

4. **Response Processing:**
   - The response from the datasource is processed by the `process_response` function to format it based on the return type.

5. **Output:**
   - The formatted response is returned as the final output.

## Endpoints Used/Created

This file does not explicitly define or call any endpoints. The primary interaction is with the datasource object, which is expected to have `predict` and `search` methods. The specifics of these methods and their interactions with external systems are not detailed in this file.