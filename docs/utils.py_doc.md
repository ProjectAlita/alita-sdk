# utils.py

**Path:** `src/alita_sdk/langchain/utils.py`

## Data Flow

The data flow within `utils.py` primarily revolves around the extraction, parsing, and transformation of JSON data. The journey begins with raw JSON strings, which are processed through various functions to extract meaningful data. The `_find_json_bounds` function identifies the start and end positions of JSON objects within a string. This is followed by `_extract_json`, which uses these bounds to extract and parse the JSON data. If the JSON extraction fails, `_extract_using_regex` attempts to parse the data using regular expressions. The `unpack_json` function orchestrates these operations, ensuring robust handling of JSON data. Additionally, functions like `create_state` and `create_typed_dict_from_yaml` transform input data into structured formats like `TypedDict` and Pydantic models. The data flow is characterized by a series of transformations, from raw strings to structured data formats, ensuring data integrity and usability.

Example:
```python
def _extract_json(json_string: str) -> dict:
    json_start, json_end = _find_json_bounds(json_string)

    if json_start is None or json_end is None:
        logger.error(f'Cannot parse json string: {json_string}')
        raise ValueError('Cannot parse json string')

    json_str = json_string[json_start:json_end]
    return json.loads(json_str)
```
In this example, the `_extract_json` function extracts and parses JSON data from a string, ensuring that only valid JSON is processed.

## Functions Descriptions

1. **_find_json_bounds**: Identifies the start and end positions of JSON objects within a string. It uses a stack to track the opening and closing braces, ensuring accurate identification of JSON boundaries.
   - **Inputs**: `json_string` (str)
   - **Outputs**: Tuple of start and end positions (int, int) or (None, None)

2. **_extract_json**: Extracts and parses JSON data from a string using the bounds identified by `_find_json_bounds`.
   - **Inputs**: `json_string` (str)
   - **Outputs**: Parsed JSON data (dict)

3. **_extract_using_regex**: Uses regular expressions to extract specific fields from a JSON-like string. It handles nested structures and special characters.
   - **Inputs**: `text` (str)
   - **Outputs**: Extracted data (dict)

4. **_old_extract_json**: Extracts JSON data from a string using a regex pattern. It handles embedded JSON within text and updates message keys if provided.
   - **Inputs**: `json_data` (str), `message_key` (optional)
   - **Outputs**: Parsed JSON data (dict)

5. **_unpack_json**: Unpacks JSON data, handling both string and dictionary inputs. It uses `_extract_json` and `_extract_using_regex` for robust parsing.
   - **Inputs**: `json_data` (str or dict), `kwargs` (optional)
   - **Outputs**: Unpacked JSON data (dict)

6. **unpack_json**: Wrapper function for `_unpack_json`, adding error handling and logging. It ensures robust JSON unpacking and handles newline characters.
   - **Inputs**: `json_data` (str or dict), `kwargs` (optional)
   - **Outputs**: Unpacked JSON data (dict)

7. **parse_type**: Parses a type string into an actual Python type using `eval`. It handles built-in and globally defined types.
   - **Inputs**: `type_str` (str)
   - **Outputs**: Parsed type (Any)

8. **create_state**: Creates a `TypedDict` representing the state, based on input data. It handles various data types and annotations.
   - **Inputs**: `data` (optional dict)
   - **Outputs**: `TypedDict` representing the state

9. **create_typed_dict_from_yaml**: Creates a `TypedDict` from YAML data, parsing attribute types and constructing the class dynamically.
   - **Inputs**: `data` (dict)
   - **Outputs**: `TypedDict` class

10. **propagate_the_input_mapping**: Maps input variables to their corresponding values in the state, handling different types of mappings (fstring, fixed, etc.).
    - **Inputs**: `input_mapping` (dict), `input_variables` (list), `state` (dict)
    - **Outputs**: Mapped input data (dict)

11. **create_pydantic_model**: Dynamically creates a Pydantic model based on input variables and their types. It uses `parse_type` to handle type parsing.
    - **Inputs**: `model_name` (str), `variables` (dict)
    - **Outputs**: Pydantic model class

## Dependencies Used and Their Descriptions

1. **builtins**: Provides access to Python's built-in functions and types, used for evaluating type strings in `parse_type`.
2. **json**: Standard library for JSON parsing and manipulation, used extensively for extracting and unpacking JSON data.
3. **logging**: Standard library for logging error messages and debugging information, used for error handling and debugging.
4. **re**: Standard library for regular expressions, used in `_extract_using_regex` to parse JSON-like strings.
5. **pydantic**: Library for data validation and settings management using Python type annotations, used in `create_pydantic_model` to create dynamic models.
6. **typing**: Standard library for type hints, used for type annotations in function signatures and return types.
7. **langchain_core.messages**: Provides the `AnyMessage` type, used in `create_state` for message handling.
8. **langchain_core.prompts**: Provides the `PromptTemplate` type, although not directly used in the provided code.
9. **langgraph.graph**: Provides `MessagesState` and `add_messages`, used in `create_state` for handling message states.

## Functional Flow

The functional flow in `utils.py` is centered around the robust handling and transformation of JSON data. The process begins with the identification of JSON boundaries using `_find_json_bounds`, followed by the extraction and parsing of JSON data through `_extract_json` and `_extract_using_regex`. The `unpack_json` function serves as the main orchestrator, ensuring that JSON data is correctly unpacked and parsed, with error handling and logging integrated for robustness. Additional functions like `create_state`, `create_typed_dict_from_yaml`, and `create_pydantic_model` provide utilities for transforming input data into structured formats, enhancing data integrity and usability. The flow is characterized by a series of transformations and validations, ensuring that input data is accurately processed and converted into the desired formats.

Example:
```python
def unpack_json(json_data: str | dict, **kwargs) -> dict:
    try:
        return _unpack_json(json_data, **kwargs)
    except json.JSONDecodeError as e:
        logger.error(f"Error in unpacking json with regex: {json_data}")
        if isinstance(json_data, str):
            return _unpack_json(json_data.replace("\n", "\\n"), **kwargs)
        raise e
```
In this example, the `unpack_json` function demonstrates the functional flow of handling JSON data, with error handling and logging integrated for robustness.

## Endpoints Used/Created

The `utils.py` file does not explicitly define or call any external endpoints. Its primary focus is on the extraction, parsing, and transformation of JSON data, as well as the creation of structured data formats like `TypedDict` and Pydantic models. The functions within this file operate on input data and return processed results, without interacting with external APIs or endpoints.