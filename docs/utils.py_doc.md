# utils.py

**Path:** `src/alita_sdk/langchain/utils.py`

## Data Flow

The data flow within `utils.py` is primarily concerned with extracting and processing JSON data from strings. The journey of data begins with raw JSON strings, which are then parsed and transformed into Python dictionaries. The data flow can be summarized as follows:

1. **Input:** Raw JSON strings are provided as input to various functions.
2. **Processing:** Functions like `_find_json_bounds`, `_extract_json`, and `_extract_using_regex` process these strings to identify and extract JSON data. Intermediate variables such as `json_start`, `json_end`, and `args_dict` are used to temporarily store data during processing.
3. **Output:** The processed data is returned as Python dictionaries, which can then be used by other parts of the application.

Example:
```python
# Example of extracting JSON data from a string
json_string = '{"key": "value"}'
json_data = _extract_json(json_string)
# json_data now contains the dictionary: {'key': 'value'}
```

## Functions Descriptions

### `_find_json_bounds`

This function identifies the start and end positions of a JSON object within a string. It uses a stack to keep track of opening and closing braces.

- **Inputs:** A JSON string (`json_string`)
- **Processing:** Iterates through the string, using a stack to track braces and identify the bounds of the JSON object.
- **Outputs:** A tuple containing the start and end positions of the JSON object.

### `_extract_json`

This function extracts a JSON object from a string using the bounds identified by `_find_json_bounds`.

- **Inputs:** A JSON string (`json_string`)
- **Processing:** Calls `_find_json_bounds` to get the bounds, then slices the string and parses the JSON data.
- **Outputs:** A Python dictionary containing the JSON data.

### `_extract_using_regex`

This function extracts specific fields from a JSON string using regular expressions.

- **Inputs:** A text string (`text`)
- **Processing:** Uses regular expressions to find and extract specific fields like `text`, `plan`, `criticism`, `name`, and `args`.
- **Outputs:** A dictionary containing the extracted fields.

### `_old_extract_json`

This function extracts JSON data from a string using a different approach, primarily for backward compatibility.

- **Inputs:** A JSON string (`json_data`), an optional message key (`message_key`)
- **Processing:** Uses regular expressions to find JSON data within code blocks, then parses the JSON data.
- **Outputs:** A Python dictionary containing the JSON data.

### `_unpack_json`

This function unpacks JSON data from a string or dictionary, using `_extract_json` and `_extract_using_regex` as needed.

- **Inputs:** JSON data (`json_data`), additional keyword arguments (`kwargs`)
- **Processing:** Tries to parse the JSON data using `_extract_json` and `_extract_using_regex`, handling errors as needed.
- **Outputs:** A Python dictionary containing the unpacked JSON data.

### `unpack_json`

This function is a wrapper around `_unpack_json`, adding error handling and logging.

- **Inputs:** JSON data (`json_data`), additional keyword arguments (`kwargs`)
- **Processing:** Calls `_unpack_json` and handles any `json.JSONDecodeError` exceptions, logging errors as needed.
- **Outputs:** A Python dictionary containing the unpacked JSON data.

### `parse_type`

This function parses a type string into an actual Python type.

- **Inputs:** A type string (`type_str`)
- **Processing:** Uses `eval` to parse the type string, handling any exceptions.
- **Outputs:** The parsed Python type.

### `create_state`

This function creates a `TypedDict` representing the state, based on the provided data.

- **Inputs:** An optional dictionary (`data`)
- **Processing:** Iterates through the data, parsing types and adding them to the state dictionary.
- **Outputs:** A `TypedDict` representing the state.

### `create_typed_dict_from_yaml`

This function creates a `TypedDict` from YAML data.

- **Inputs:** YAML data (`data`)
- **Processing:** Extracts the class name and attributes from the YAML data, then creates a `TypedDict` class.
- **Outputs:** The created `TypedDict` class.

### `create_params`

This function creates a dictionary of parameters based on input variables and state.

- **Inputs:** A list of input variables (`input_variables`), a state dictionary (`state`)
- **Processing:** Iterates through the input variables, extracting values from the state and formatting them as needed.
- **Outputs:** A dictionary of parameters.

### `propagate_the_input_mapping`

This function propagates the input mapping based on the provided input variables and state.

- **Inputs:** An input mapping dictionary (`input_mapping`), a list of input variables (`input_variables`), a state dictionary (`state`)
- **Processing:** Iterates through the input mapping, creating parameters and adding them to the input data.
- **Outputs:** A dictionary of input data.

### `create_pydantic_model`

This function creates a Pydantic model based on the provided model name and variables.

- **Inputs:** A model name (`model_name`), a dictionary of variables (`variables`)
- **Processing:** Iterates through the variables, parsing types and creating fields for the Pydantic model.
- **Outputs:** The created Pydantic model.

## Dependencies Used and Their Descriptions

### `builtins`

- **Purpose:** Provides access to Python's built-in functions and types.
- **Usage:** Used in the `parse_type` function to evaluate type strings.

### `json`

- **Purpose:** Provides functions for parsing and manipulating JSON data.
- **Usage:** Used throughout the file for parsing JSON strings and converting them to Python dictionaries.

### `logging`

- **Purpose:** Provides functions for logging messages.
- **Usage:** Used for logging errors and other messages in various functions.

### `re`

- **Purpose:** Provides functions for working with regular expressions.
- **Usage:** Used in the `_extract_using_regex` and `_old_extract_json` functions to extract data from strings.

### `pydantic`

- **Purpose:** Provides data validation and settings management using Python type annotations.
- **Usage:** Used in the `create_pydantic_model` function to create Pydantic models.

### `typing`

- **Purpose:** Provides type hints and type-related utilities.
- **Usage:** Used throughout the file for type annotations.

### `langchain_core.messages`

- **Purpose:** Provides message-related classes and functions.
- **Usage:** Used in the `create_state` function to define the type of messages in the state.

### `langchain_core.prompts`

- **Purpose:** Provides prompt-related classes and functions.
- **Usage:** Not explicitly used in the provided code, but likely related to the overall functionality.

### `langgraph.graph`

- **Purpose:** Provides graph-related classes and functions.
- **Usage:** Used in the `create_state` function to add messages to the state.

## Functional Flow

The functional flow of `utils.py` revolves around the extraction and processing of JSON data. The sequence of operations is as follows:

1. **JSON Extraction:** Functions like `_find_json_bounds`, `_extract_json`, and `_extract_using_regex` are used to extract JSON data from strings.
2. **JSON Unpacking:** The `_unpack_json` and `unpack_json` functions are used to unpack JSON data, handling errors and logging messages as needed.
3. **Type Parsing:** The `parse_type` function is used to parse type strings into actual Python types.
4. **State Creation:** The `create_state` and `create_typed_dict_from_yaml` functions are used to create `TypedDict` representations of the state.
5. **Parameter Creation:** The `create_params` and `propagate_the_input_mapping` functions are used to create dictionaries of parameters based on input variables and state.
6. **Pydantic Model Creation:** The `create_pydantic_model` function is used to create Pydantic models based on the provided model name and variables.

## Endpoints Used/Created

The provided file does not explicitly define or call any endpoints. The functionality is focused on processing JSON data and creating data models, rather than interacting with external services or APIs.