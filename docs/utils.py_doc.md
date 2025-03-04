# utils.py

**Path:** `src/alita_sdk/langchain/utils.py`

## Data Flow

The data flow within `utils.py` primarily revolves around the extraction and manipulation of JSON data from strings. The journey begins with the input of a JSON string, which is then processed to identify the bounds of the JSON object within the string. This is achieved through the `_find_json_bounds` function, which uses a stack-based approach to locate the start and end of the JSON object. Once the bounds are identified, the `_extract_json` function extracts the JSON substring and parses it into a Python dictionary using the `json.loads` method.

An alternative method for extraction is provided by `_extract_using_regex`, which uses regular expressions to identify and extract specific components of the JSON data. This method is particularly useful when the JSON data is embedded within a larger text block and needs to be isolated based on patterns.

The extracted JSON data is then further processed by functions like `_unpack_json` and `unpack_json`, which handle different formats and potential errors during the extraction process. These functions ensure that the JSON data is correctly parsed and returned as a dictionary, ready for further use in the application.

Example:
```python
# Example of extracting JSON data from a string
json_string = '{"key": "value"}'
parsed_data = _extract_json(json_string)
print(parsed_data)  # Output: {'key': 'value'}
```

## Functions Descriptions

1. **_find_json_bounds(json_string: str) -> Tuple[int, int] | Tuple[None, None]**
   - **Purpose:** Identifies the start and end positions of a JSON object within a string.
   - **Inputs:** A string containing JSON data.
   - **Outputs:** A tuple containing the start and end positions of the JSON object, or (None, None) if not found.
   - **Example:**
   ```python
   bounds = _find_json_bounds('{"key": "value"}')
   print(bounds)  # Output: (0, 15)
   ```

2. **_extract_json(json_string: str) -> dict**
   - **Purpose:** Extracts and parses a JSON object from a string.
   - **Inputs:** A string containing JSON data.
   - **Outputs:** A dictionary representing the parsed JSON data.
   - **Example:**
   ```python
   parsed_data = _extract_json('{"key": "value"}')
   print(parsed_data)  # Output: {'key': 'value'}
   ```

3. **_extract_using_regex(text: str) -> dict**
   - **Purpose:** Extracts JSON components from a string using regular expressions.
   - **Inputs:** A string containing JSON data.
   - **Outputs:** A dictionary representing the extracted JSON components.
   - **Example:**
   ```python
   extracted_data = _extract_using_regex('{"key": "value"}')
   print(extracted_data)  # Output: {'key': 'value'}
   ```

4. **_unpack_json(json_data: str | dict, **kwargs) -> dict**
   - **Purpose:** Unpacks JSON data from a string or dictionary, handling different formats and errors.
   - **Inputs:** A string or dictionary containing JSON data.
   - **Outputs:** A dictionary representing the unpacked JSON data.
   - **Example:**
   ```python
   unpacked_data = _unpack_json('{"key": "value"}')
   print(unpacked_data)  # Output: {'key': 'value'}
   ```

5. **unpack_json(json_data: str | dict, **kwargs) -> dict**
   - **Purpose:** Wrapper function for `_unpack_json` with additional error handling.
   - **Inputs:** A string or dictionary containing JSON data.
   - **Outputs:** A dictionary representing the unpacked JSON data.
   - **Example:**
   ```python
   unpacked_data = unpack_json('{"key": "value"}')
   print(unpacked_data)  # Output: {'key': 'value'}
   ```

6. **parse_type(type_str)**
   - **Purpose:** Parses a type string into an actual Python type.
   - **Inputs:** A string representing a type.
   - **Outputs:** The corresponding Python type.
   - **Example:**
   ```python
   parsed_type = parse_type('int')
   print(parsed_type)  # Output: <class 'int'>
   ```

7. **create_state(data: Optional[dict] = None)**
   - **Purpose:** Creates a state dictionary with specified types.
   - **Inputs:** An optional dictionary containing state data.
   - **Outputs:** A TypedDict representing the state.
   - **Example:**
   ```python
   state = create_state({'messages': 'list[str]'})
   print(state)  # Output: {'input': <class 'str'>, 'messages': typing.Annotated[list, <function add_messages at 0x...>]}
   ```

8. **create_typed_dict_from_yaml(data)**
   - **Purpose:** Creates a TypedDict from YAML data.
   - **Inputs:** A dictionary representing YAML data.
   - **Outputs:** A TypedDict class.
   - **Example:**
   ```python
   yaml_data = {'MyClass': {'attr1': 'str', 'attr2': 'int'}}
   typed_dict = create_typed_dict_from_yaml(yaml_data)
   print(typed_dict)  # Output: <class 'MyClass'>
   ```

9. **create_params(input_variables: list[str], state: dict) -> dict**
   - **Purpose:** Creates a dictionary of parameters from input variables and state data.
   - **Inputs:** A list of input variables and a state dictionary.
   - **Outputs:** A dictionary of parameters.
   - **Example:**
   ```python
   params = create_params(['messages'], {'messages': ['Hello', 'World']})
   print(params)  # Output: {'messages': 'Hello\nWorld'}
   ```

10. **propagate_the_input_mapping(input_mapping: dict[str, dict], input_variables: list[str], state: dict) -> dict**
    - **Purpose:** Propagates input mapping to create a dictionary of input data.
    - **Inputs:** An input mapping dictionary, a list of input variables, and a state dictionary.
    - **Outputs:** A dictionary of input data.
    - **Example:**
    ```python
    input_mapping = {'var1': {'type': 'fstring', 'value': '{messages}'}}
    input_data = propagate_the_input_mapping(input_mapping, ['messages'], {'messages': ['Hello', 'World']})
    print(input_data)  # Output: {'var1': 'Hello\nWorld'}
    ```

11. **create_pydantic_model(model_name: str, variables: dict[str, dict])**
    - **Purpose:** Creates a Pydantic model from a dictionary of variables.
    - **Inputs:** A model name and a dictionary of variables.
    - **Outputs:** A Pydantic model class.
    - **Example:**
    ```python
    variables = {'var1': {'type': 'str', 'description': 'A string variable'}}
    model = create_pydantic_model('MyModel', variables)
    print(model)  # Output: <class 'MyModel'>
    ```

## Dependencies Used and Their Descriptions

1. **builtins**
   - **Purpose:** Provides access to Python's built-in functions and types.
   - **Usage:** Used in the `parse_type` function to evaluate type strings.

2. **json**
   - **Purpose:** Provides functions for parsing and manipulating JSON data.
   - **Usage:** Used extensively for loading and dumping JSON data in various functions.

3. **logging**
   - **Purpose:** Provides a flexible framework for emitting log messages from Python programs.
   - **Usage:** Used for logging errors and information throughout the module.

4. **re**
   - **Purpose:** Provides support for regular expressions in Python.
   - **Usage:** Used in `_extract_using_regex` to identify and extract JSON components from strings.

5. **pydantic**
   - **Purpose:** Provides data validation and settings management using Python type annotations.
   - **Usage:** Used in `create_pydantic_model` to create Pydantic models dynamically.

6. **typing**
   - **Purpose:** Provides support for type hints in Python.
   - **Usage:** Used for type annotations throughout the module.

7. **langchain_core.messages**
   - **Purpose:** Provides message handling capabilities for LangChain.
   - **Usage:** Used in `create_state` to define the type of messages in the state.

8. **langchain_core.prompts**
   - **Purpose:** Provides prompt templates for LangChain.
   - **Usage:** Not directly used in the provided code but imported for potential use.

9. **langgraph.graph**
   - **Purpose:** Provides graph-related functionalities for LangGraph.
   - **Usage:** Used in `create_state` to annotate the messages list with `add_messages`.

## Functional Flow

The functional flow of `utils.py` begins with the extraction of JSON data from strings. The primary functions involved in this process are `_find_json_bounds`, `_extract_json`, and `_extract_using_regex`. These functions work together to identify, extract, and parse JSON data from strings, handling different formats and potential errors.

Once the JSON data is extracted, it is further processed by functions like `_unpack_json` and `unpack_json`, which ensure that the data is correctly parsed and returned as a dictionary. These functions also handle different input formats and provide error handling to ensure robustness.

Additional utility functions like `parse_type`, `create_state`, `create_typed_dict_from_yaml`, `create_params`, `propagate_the_input_mapping`, and `create_pydantic_model` provide support for type parsing, state creation, and dynamic model generation. These functions enhance the flexibility and usability of the module, allowing it to handle a wide range of input data and configurations.

## Endpoints Used/Created

The `utils.py` module does not explicitly define or call any endpoints. Its primary focus is on data extraction, parsing, and utility functions for handling JSON data and dynamic type creation.