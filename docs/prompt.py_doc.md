# prompt.py

**Path:** `src/alita_sdk/tools/prompt.py`

## Data Flow

The data flow within `prompt.py` begins with the importation of necessary modules and functions, such as `logging`, `BaseTool` from `langchain_core.tools`, `field_validator` from `pydantic`, and `clean_string` from `..utils.utils`. The primary class in this file, `Prompt`, is a subclass of `BaseTool` and is designed to handle prompt-related operations. The data flow can be summarized as follows:

1. **Initialization:** The `Prompt` class is initialized with attributes like `name`, `description`, `prompt`, and `return_type`. The `name` attribute undergoes validation to remove spaces using the `clean_string` function.
2. **Processing:** The `_run` method is called with keyword arguments, which are passed to the `prompt.predict` method. The result is then processed by the `process_response` function based on the `return_type`.
3. **Output:** The processed response is returned as either a string or a dictionary containing a message.

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
In this example, the `Prompt` class is defined with its attributes and methods, showcasing the data flow from initialization to output.

## Functions Descriptions

### `process_response`

This function processes the response based on the `return_type`. If the `return_type` is "str", it returns the response as is. Otherwise, it returns a dictionary with the response wrapped in a specific format.

**Parameters:**
- `response`: The response to be processed.
- `return_type`: The type to which the response should be converted.

**Returns:**
- Processed response as a string or dictionary.

Example:
```python
def process_response(response, return_type):
    if return_type == "str":
        return response
    else:
        return {"messages": [{"role": "assistant", "content": response}]}
```

### `Prompt`

This class inherits from `BaseTool` and represents a prompt with attributes like `name`, `description`, `prompt`, and `return_type`. It includes a field validator for the `name` attribute and a `_run` method to execute the prompt.

**Attributes:**
- `name`: The name of the prompt.
- `description`: A brief description of the prompt.
- `prompt`: The prompt object.
- `return_type`: The type of the response (default is "str").

**Methods:**
- `remove_spaces`: A class method to remove spaces from the `name` attribute using the `clean_string` function.
- `_run`: Executes the prompt and processes the response.

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

## Dependencies Used and Their Descriptions

### `logging`

The `logging` module is used to set up a logger for the file. This is useful for tracking events that happen when some software runs.

### `BaseTool`

Imported from `langchain_core.tools`, `BaseTool` is the base class for creating tools in the LangChain framework. The `Prompt` class inherits from this base class.

### `field_validator`

Imported from `pydantic`, `field_validator` is used to validate fields in Pydantic models. In this file, it is used to validate the `name` attribute of the `Prompt` class.

### `clean_string`

Imported from `..utils.utils`, `clean_string` is a utility function used to clean and format strings. It is used in the `remove_spaces` method to clean the `name` attribute.

## Functional Flow

1. **Imports and Logger Setup:** The file begins with importing necessary modules and setting up a logger.
2. **Function Definition:** The `process_response` function is defined to process the response based on the `return_type`.
3. **Class Definition:** The `Prompt` class is defined with its attributes and methods.
4. **Field Validation:** The `remove_spaces` method is defined to clean the `name` attribute using the `clean_string` function.
5. **Run Method:** The `_run` method is defined to execute the prompt and process the response.

Example:
```python
import logging
from langchain_core.tools import BaseTool
from pydantic import field_validator
from typing import Any
from ..utils.utils import clean_string

logger = logging.getLogger(__name__)

def process_response(response, return_type):
    if return_type == "str":
        return response
    else:
        return {"messages": [{"role": "assistant", "content": response}]}

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

## Endpoints Used/Created

No explicit endpoints are defined or used within this file.