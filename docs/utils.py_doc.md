# utils.py

**Path:** `src/alita_sdk/langchain/utils.py`

## Data Flow

The data flow within `utils.py` primarily revolves around the extraction, parsing, and transformation of JSON data. The journey of data begins with raw JSON strings, which are then processed through various functions to extract meaningful information. The data is transformed from a raw string format into structured Python dictionaries. The functions `_find_json_bounds`, `_extract_json`, `_extract_using_regex`, and `_unpack_json` play crucial roles in this transformation process. The data flow can be summarized as follows:

1. **Input:** Raw JSON string.
2. **Processing:** The JSON string is passed through functions to identify the bounds, extract the JSON content, and parse it into a dictionary.
3. **Output:** A structured Python dictionary containing the extracted data.

Example:
```python
json_string = '{"key": "value"}'
parsed_data = _extract_json(json_string)
# parsed_data now contains {'key': 'value'}
```

## Functions Descriptions

### `_find_json_bounds`

This function identifies the start and end positions of a JSON object within a string. It uses a stack-based approach to match opening and closing braces.

**Inputs:**
- `json_string` (str): The input string containing JSON data.

**Outputs:**
- Tuple[int, int] | Tuple[None, None]: The start and end positions of the JSON object, or (None, None) if not found.

### `_extract_json`

This function extracts a JSON object from a string based on the bounds identified by `_find_json_bounds` and parses it into a dictionary.

**Inputs:**
- `json_string` (str): The input string containing JSON data.

**Outputs:**
- dict: The parsed JSON data as a dictionary.

### `_extract_using_regex`

This function uses regular expressions to extract specific fields from a JSON-like string. It identifies fields such as `text`, `plan`, `criticism`, `name`, and `args`.

**Inputs:**
- `text` (str): The input string containing JSON-like data.

**Outputs:**
- dict: A dictionary containing the extracted fields.

### `_unpack_json`

This function attempts to parse a JSON string or dictionary. It first tries to use `_extract_json`, and if that fails, it falls back to `_extract_using_regex`.

**Inputs:**
- `json_data` (str | dict): The input JSON data.

**Outputs:**
- dict: The parsed JSON data as a dictionary.

### `unpack_json`

This function is a wrapper around `_unpack_json` that adds error handling and logging. It attempts to parse JSON data and logs errors if parsing fails.

**Inputs:**
- `json_data` (str | dict): The input JSON data.

**Outputs:**
- dict: The parsed JSON data as a dictionary.

### `parse_type`

This function parses a type string into an actual Python type using `eval`.

**Inputs:**
- `type_str` (str): The type string to parse.

**Outputs:**
- type: The parsed Python type.

### `create_state`

This function creates a `TypedDict` representing the state based on the provided data dictionary.

**Inputs:**
- `data` (Optional[dict]): The input data dictionary.

**Outputs:**
- TypedDict: The created state as a `TypedDict`.

### `create_typed_dict_from_yaml`

This function creates a `TypedDict` from a YAML-like dictionary.

**Inputs:**
- `data` (dict): The input YAML-like dictionary.

**Outputs:**
- TypedDict: The created `TypedDict`.

### `propagate_the_input_mapping`

This function propagates input mappings to create a dictionary of input data based on the state.

**Inputs:**
- `input_mapping` (dict[str, dict]): The input mapping dictionary.
- `input_variables` (list[str]): The list of input variables.
- `state` (dict): The current state dictionary.

**Outputs:**
- dict: The propagated input data.

### `create_pydantic_model`

This function creates a Pydantic model based on the provided model name and variables.

**Inputs:**
- `model_name` (str): The name of the model.
- `variables` (dict[str, dict]): The dictionary of variables.

**Outputs:**
- Pydantic model: The created Pydantic model.

## Dependencies Used and Their Descriptions

### `builtins`

Used for evaluating type strings in the `parse_type` function.

### `json`

Used for parsing JSON data in various functions.

### `logging`

Used for logging errors and information.

### `re`

Used for regular expression matching in the `_extract_using_regex` function.

### `pydantic`

Used for creating Pydantic models in the `create_pydantic_model` function.

### `typing`

Used for type annotations.

### `langchain_core.messages`

Used for handling messages in the `create_state` function.

### `langchain_core.prompts`

Used for handling prompts.

### `langgraph.graph`

Used for managing message states and adding messages.

## Functional Flow

The functional flow of `utils.py` involves the following steps:

1. **JSON Extraction:** Functions like `_find_json_bounds` and `_extract_json` are used to extract JSON data from strings.
2. **Data Parsing:** The extracted JSON data is parsed into Python dictionaries using functions like `_unpack_json` and `unpack_json`.
3. **Type Parsing:** The `parse_type` function is used to parse type strings into actual Python types.
4. **State Creation:** The `create_state` function creates a `TypedDict` representing the state based on the provided data.
5. **Input Mapping:** The `propagate_the_input_mapping` function propagates input mappings to create a dictionary of input data based on the state.
6. **Model Creation:** The `create_pydantic_model` function creates a Pydantic model based on the provided model name and variables.

## Endpoints Used/Created

No explicit endpoints are defined or used within `utils.py`.