# prompt.py

**Path:** `src/alita_sdk/tools/prompt.py`

## Data Flow

The data flow within `prompt.py` begins with the importation of necessary modules and functions, such as `logging`, `BaseTool` from `langchain_core.tools`, `field_validator` from `pydantic`, and `clean_string` from `..utils.utils`. The primary class in this file, `Prompt`, is designed to handle prompt-based operations. Data enters the class through its attributes (`name`, `description`, `prompt`, and `return_type`). The `process_response` function processes the response based on the `return_type`. If the `return_type` is a string, it returns the response directly; otherwise, it formats the response into a dictionary. The `_run` method uses the `prompt` attribute to predict outcomes based on provided variables (`kwargs`) and processes the response accordingly. Intermediate variables like `response` and `return_type` are used to temporarily store data during processing.

Example:
```python
class Prompt(BaseTool):
    name: str
    description: str
    prompt: Any
    return_type: str = "str"
    
    @field_validator('name', mode='before')
    @classmethod
    def remove_spaces(cls, v):
        return clean_string(v)
    
    def _run(self, **kwargs):
        return process_response(self.prompt.predict(variables=kwargs), self.return_type)
```
In this example, the `Prompt` class processes data through its `_run` method, predicting outcomes and formatting responses based on the `return_type`.

## Functions Descriptions

1. **process_response(response, return_type):**
   - **Purpose:** Processes the response based on the specified return type.
   - **Inputs:** `response` (the response to process), `return_type` (the type to return, either "str" or a dictionary).
   - **Outputs:** Returns the response as a string or a formatted dictionary.
   - **Logic:** Checks the `return_type` and returns the response accordingly.

2. **remove_spaces(cls, v):**
   - **Purpose:** Removes spaces from the input string.
   - **Inputs:** `v` (the string to clean).
   - **Outputs:** Returns the cleaned string.
   - **Logic:** Uses the `clean_string` function to remove spaces.

3. **_run(self, **kwargs):**
   - **Purpose:** Runs the prompt prediction and processes the response.
   - **Inputs:** `kwargs` (variables for the prompt prediction).
   - **Outputs:** Returns the processed response.
   - **Logic:** Uses the `prompt` attribute to predict outcomes and processes the response using `process_response`.

## Dependencies Used and Their Descriptions

1. **logging:**
   - **Purpose:** Provides logging capabilities to track events and errors.
   - **Usage:** Used to create a logger instance for the module.

2. **BaseTool (from langchain_core.tools):**
   - **Purpose:** Serves as the base class for the `Prompt` class.
   - **Usage:** Inherited by the `Prompt` class to provide core functionalities.

3. **field_validator (from pydantic):**
   - **Purpose:** Provides validation for model fields.
   - **Usage:** Used to validate and clean the `name` attribute of the `Prompt` class.

4. **clean_string (from ..utils.utils):**
   - **Purpose:** Cleans input strings by removing spaces.
   - **Usage:** Used in the `remove_spaces` method to clean the `name` attribute.

## Functional Flow

The functional flow of `prompt.py` starts with the definition of the `process_response` function, which processes responses based on the `return_type`. The `Prompt` class is then defined, inheriting from `BaseTool`. The class includes attributes for `name`, `description`, `prompt`, and `return_type`, with default values and type hints. The `remove_spaces` method is defined as a class method to clean the `name` attribute before validation. The `_run` method is the core function that predicts outcomes using the `prompt` attribute and processes the response using the `process_response` function. The flow involves initializing the `Prompt` class with the necessary attributes, running the `_run` method with provided variables, and processing the response based on the `return_type`.

## Endpoints Used/Created

There are no explicit endpoints defined or used within `prompt.py`. The file focuses on defining the `Prompt` class and its methods for handling prompt-based operations.