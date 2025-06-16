import json
import re
from typing import Type, Any, Callable, TypeVar

from pydantic import BaseModel

T = TypeVar('T', bound=BaseModel)


class OutputParserError(Exception):
    """
    Exception raised when the output parser fails to parse the output.
    """
    def __init__(self, message, output=None):
        self.message = message
        self.output = output
        super().__init__(self.message)
        
    def __str__(self):
        if self.output:
            return f"{self.message}\nProblematic output: {self.output}"
        return self.message


def find_json_in_string(string: str) -> str:
    """
    Method to extract all text in the left-most brace that appears in a string.
    Used to extract JSON from a string (note that this function does not validate the JSON).

    Example:
        string = "bla bla bla {this is {some} text{{}and it's sneaky}} because {it's} confusing"
        output = "{this is {some} text{{}and it's sneaky}}"
    """
    stack = 0
    start_index = None

    for i, c in enumerate(string):
        if c == '{':
            if stack == 0:
                start_index = i  # Start index of the first '{'
            stack += 1  # Push to stack
        elif c == '}':
            stack -= 1  # Pop stack
            if stack == 0:
                # Return the substring from the start of the first '{' to the current '}'
                return string[start_index:i + 1] if start_index is not None else ""

    # If no complete set of braces is found, return an empty string
    return ""


def parse_json_output(output: str) -> Any:
    """Take a string output and parse it as JSON"""
    # First try to load the string as JSON
    try:
        return json.loads(output)
    except json.JSONDecodeError as e:
        pass

    # If that fails, assume that the output is in a code block - remove the code block markers and try again
    parsed_output = output
    parsed_output = parsed_output.split("```")[1]
    parsed_output = parsed_output.split("```")[0]
    if parsed_output.startswith("json") or parsed_output.startswith("JSON"):
        parsed_output = parsed_output[4:].strip()
    try:
        return json.loads(parsed_output)
    except json.JSONDecodeError:
        pass

    # As a last attempt, try to manually find the JSON object in the output and parse it
    parsed_output = find_json_in_string(output)
    if parsed_output:
        try:
            return json.loads(parsed_output)
        except json.JSONDecodeError:
            raise OutputParserError(f"Failed to parse output as JSON", output)

    # If all fails, raise an error
    raise OutputParserError(f"Failed to parse output as JSON", output)


def create_type_parser(model_class: Type[T]) -> Callable[[str], T]:
    """
    Creates a parser function that attempts to parse the output into the given model class.
    This handles various formats that might be returned by the LLM.
    
    Args:
        model_class: The Pydantic model class to parse the output into
        
    Returns:
        A function that takes a string and returns an instance of the model class
    """
    def parser(text: str) -> T:
        """
        Parse the output into the model class.
        
        Args:
            text: The text to parse
            
        Returns:
            An instance of the model class
        """
        # First try direct JSON parsing
        try:
            return model_class.model_validate_json(text)
        except Exception:
            pass
        
        # Try to extract JSON from markdown codeblocks
        json_match = re.search(r"```(?:json)?\n(.*?)\n```", text, re.DOTALL)
        if json_match:
            try:
                json_str = json_match.group(1).strip()
                return model_class.model_validate_json(json_str)
            except Exception:
                pass
        
        # Try to parse the entire text as a JSON object
        try:
            # Look for JSON-like patterns
            json_pattern = r"(\{.*\})"
            match = re.search(json_pattern, text, re.DOTALL)
            if match:
                json_str = match.group(1)
                parsed = json.loads(json_str)
                return model_class.model_validate(parsed)
        except Exception:
            pass
        
        # Fall back to creating an instance with the text as output
        try:
            # Check if model has 'output' field
            if 'output' in model_class.model_fields:
                return model_class(output=text)
        except Exception:
            pass
        
        # Last resort: just try to create an empty instance and set attributes
        try:
            instance = model_class()
            if hasattr(instance, 'output'):
                setattr(instance, 'output', text)
            return instance
        except Exception as e:
            raise ValueError(f"Could not parse output to {model_class.__name__}: {e}")
    
    return parser
