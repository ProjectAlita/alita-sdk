# utils.py

**Path:** `src/alita_sdk/langchain/utils.py`

## Data Flow

The data flow within `utils.py` primarily revolves around the extraction, parsing, and transformation of JSON data. The journey begins with raw JSON strings, which are processed through various functions to extract meaningful data. The `_find_json_bounds` function identifies the start and end positions of JSON objects within a string. This is followed by `_extract_json`, which uses these bounds to extract and parse the JSON data. If the JSON extraction fails, `_extract_using_regex` attempts to parse the data using regular expressions. The `_unpack_json` function consolidates these methods to handle different JSON formats and structures. The final processed data is then used by other functions or returned as output. Intermediate variables such as `json_start`, `json_end`, and `json_str` are used to temporarily store data during processing.

Example:
```python
def _find_json_bounds(json_string: str) -> Tuple[int, int] | Tuple[None, None]:
    stack = []
    json_start = None

    for i, char in enumerate(json_string):
        if char == '{':
            if not stack:
                json_start = i
            stack.append(char)
        elif char == '}':
            if stack:
                stack.pop()
                if not stack:
                    return json_start, i + 1

    return None, None
```
This function identifies the bounds of a JSON object within a string, which is crucial for subsequent extraction and parsing.

## Functions Descriptions

1. **_find_json_bounds**: Identifies the start and end positions of JSON objects within a string. It uses a stack to track the opening and closing braces.
   - **Inputs**: `json_string` (str)
   - **Outputs**: Tuple of start and end positions (int, int) or (None, None)

2. **_extract_json**: Extracts and parses JSON data from a string using the bounds identified by `_find_json_bounds`.
   - **Inputs**: `json_string` (str)
   - **Outputs**: Parsed JSON data (dict)

3. **_extract_using_regex**: Uses regular expressions to extract specific fields from a JSON-like string.
   - **Inputs**: `text` (str)
   - **Outputs**: Extracted data (dict)

4. **_old_extract_json**: Extracts JSON data from a string using a regex pattern for older formats.
   - **Inputs**: `json_data` (str), `message_key` (optional)
   - **Outputs**: Parsed JSON data (dict)

5. **_unpack_json**: Consolidates different methods to handle various JSON formats and structures.
   - **Inputs**: `json_data` (str or dict), `kwargs`
   - **Outputs**: Parsed JSON data (dict)

6. **unpack_json**: Wrapper for `_unpack_json` with additional error handling.
   - **Inputs**: `json_data` (str or dict), `kwargs`
   - **Outputs**: Parsed JSON data (dict)

7. **parse_type**: Parses a type string into an actual Python type.
   - **Inputs**: `type_str` (str)
   - **Outputs**: Parsed type (Any)

8. **create_state**: Creates a state dictionary with specified types.
   - **Inputs**: `data` (optional dict)
   - **Outputs**: State dictionary (TypedDict)

9. **create_typed_dict_from_yaml**: Creates a TypedDict class from YAML data.
   - **Inputs**: `data` (dict)
   - **Outputs**: TypedDict class

10. **propagate_the_input_mapping**: Maps input variables to their corresponding values in the state.
    - **Inputs**: `input_mapping` (dict), `input_variables` (list), `state` (dict)
    - **Outputs**: Mapped input data (dict)

11. **create_pydantic_model**: Creates a Pydantic model from specified variables.
    - **Inputs**: `model_name` (str), `variables` (dict)
    - **Outputs**: Pydantic model

## Dependencies Used and Their Descriptions

1. **builtins**: Used for evaluating type strings in `parse_type`.
2. **json**: Used for parsing JSON data in various functions.
3. **logging**: Used for logging errors and information.
4. **re**: Used for regular expression operations in `_extract_using_regex`.
5. **pydantic**: Used for creating Pydantic models in `create_pydantic_model`.
6. **typing**: Used for type annotations and TypedDict.
7. **langchain_core.messages**: Used for handling messages in `create_state`.
8. **langchain_core.prompts**: Used for prompt templates.
9. **langgraph.graph**: Used for managing message states and adding messages.

## Functional Flow

The functional flow of `utils.py` starts with the extraction and parsing of JSON data. The `_find_json_bounds` function identifies the bounds of JSON objects, followed by `_extract_json` which parses the JSON data. If this fails, `_extract_using_regex` attempts to extract data using regular expressions. The `_unpack_json` function consolidates these methods to handle different JSON formats. The `unpack_json` function acts as a wrapper with additional error handling. Other functions like `parse_type`, `create_state`, and `create_typed_dict_from_yaml` provide utility operations for type parsing and state management. The `propagate_the_input_mapping` function maps input variables to their corresponding values in the state, and `create_pydantic_model` creates Pydantic models from specified variables.

## Endpoints Used/Created

No explicit endpoints are defined or called within `utils.py`. The file primarily focuses on utility functions for JSON extraction, parsing, and type handling.