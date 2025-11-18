import builtins
import json
import logging
import re
from pydantic import create_model, Field
from typing import Tuple, TypedDict, Any, Optional, Annotated
from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages

from ...runtime.langchain.constants import ELITEA_RS

logger = logging.getLogger(__name__)


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


def _extract_json(json_string: str) -> dict:
    json_start, json_end = _find_json_bounds(json_string)

    if json_start is None or json_end is None:
        logger.error(f'Cannot parse json string: {json_string}')
        raise ValueError('Cannot parse json string')

    json_str = json_string[json_start:json_end]
    return json.loads(json_str)


def _extract_using_regex(text: str) -> dict:
    def extract_group(pattern):
        match = re.search(pattern, text, re.DOTALL)
        return match.group(1) if match else None

    thoughts_text = extract_group(r'"text": "(.*?)",')
    thoughts_plan = extract_group(r'"plan": "(.*?)",')
    thoughts_criticism = extract_group(r'"criticism": "(.*?)"\s*},')

    tool_name = extract_group(r'"name": "(.*?)"')
    args_dict = {}
    args_block_match = re.search(r'"args":\s*{(.+?)}\s*}', text, re.DOTALL)
    if args_block_match:
        args_block = args_block_match.group(1)
        keys = [match.group(1) for match in re.finditer(r'"(\w+)":', args_block)]
        for key in keys:
            args_pattern = r'"' + re.escape(key) + r'":\s*"(.*?)"(?:,|$)'
            args_matches = re.findall(args_pattern, args_block, re.DOTALL)
            for value in args_matches:
                args_dict[key] = value.replace('\\n', '\n')

    return {
        'thoughts': {
            'text': thoughts_text,
            'plan': thoughts_plan,
            'criticism': thoughts_criticism
        },
        'tool': {
            'name': tool_name,
            'args': args_dict
        }
    }


def _old_extract_json(json_data, message_key=None):
    pattern = r'```json(.*)```'
    matches = re.findall(pattern, json_data, re.DOTALL)
    if matches:
        json_str = matches[0].strip()
        text = json_data.replace(f'```json{json_str}```', '').strip()
        res = json.loads(json_str)
        if message_key and text:
            txt = "\n".join([match.value for match in message_key.find(res)])
            message_key.update(res, txt + text)
        return res
    else:
        return json.loads(json_data)


def _unpack_json(json_data: str | dict, **kwargs) -> dict:
    if isinstance(json_data, str):
        try:
            return _extract_json(json_data)
        except (json.JSONDecodeError, ValueError):
            try:
                _json_data = _extract_using_regex(json_data)
                if _json_data.get('thoughts', {}).get("text") or _json_data.get('tool', {}).get("name"):
                    return _json_data
                else:
                    raise json.JSONDecodeError(msg=f'Unable to parse json', pos=0, doc=str(json_data))
            except json.JSONDecodeError as e:
                raise e
    elif isinstance(json_data, dict):
        return json_data
    raise json.JSONDecodeError(msg=f'Unhandled type for decode {type(json_data)}', pos=0, doc=str(json_data))


def unpack_json(json_data: str | dict, **kwargs) -> dict:
    try:
        return _unpack_json(json_data, **kwargs)
    except json.JSONDecodeError as e:
        logger.error(f"Error in unpacking json with regex: {json_data}")
        if isinstance(json_data, str):
            return _unpack_json(json_data.replace("\n", "\\n"), **kwargs)
        raise e


def parse_type(type_str):
    """Parse a type string into an actual Python type."""
    try:
        # Evaluate the type string using builtins and imported modules
        if type_str == 'number':
            type_str = 'int'
        return eval(type_str, {**vars(builtins), **globals()})
    except Exception as e:
        print(f"Error parsing type: {e}")
        return Any


def create_state(data: Optional[dict] = None):
    state_dict = {'input': str, 'router_output': str, ELITEA_RS: str}  # Always include router_output
    types_dict = {}
    if not data:
        data = {'messages': 'list[str]'}
    for key, value in data.items():
        # support of old & new UI
        value = value['type'] if isinstance(value, dict) else value
        value = 'str' if value == 'string' else value  # normalize string type (old state support)
        if key == 'messages':
            state_dict[key] = Annotated[list[AnyMessage], add_messages]
        elif value in ['str', 'int', 'float', 'bool', 'list', 'dict', 'number', 'dict']:
            state_dict[key] = parse_type(value)

    state_dict["state_types"] = types_dict  # Default value for state_types
    types_dict["state_types"] = dict
    logger.debug(f"Created state: {state_dict}")
    return TypedDict('State', state_dict)

def create_typed_dict_from_yaml(data):
    # Extract class name and attributes
    class_name, attributes = next(iter(data.items()))

    # Create a TypedDict class
    cls = TypedDict(class_name, {attr: parse_type(attr_type) for attr, attr_type in attributes.items()})
    
    return cls

def create_params(input_variables: list[str], state: dict) -> dict:
    # TODO: Roma to fix, as message content may be a list, or a base64 or some another type
    return {
        var: '\n'.join(str(message.content) for message in state.get('messages', []))
        if var == 'messages'
        else str(state.get(var, ''))
        for var in input_variables
    }

def propagate_the_input_mapping(input_mapping: dict[str, dict], input_variables: list[str], state: dict, **kwargs) -> dict:
    input_data = {}
    for key, value in input_mapping.items():
        source_dict = value.get('source')
        if source_dict and source_dict != 'state':
            source = kwargs[source_dict]
            var_dict = source
        else:
            source = state
            var_dict = create_params(input_variables, source)

        if value['type'] == 'fstring':
            try:
                input_data[key] = value['value'].format(**var_dict)
            except KeyError as e:
                logger.error(f"KeyError in fstring formatting for key '{key}'. Attempt to find proper data in state.\n{e}")
                try:
                    # search for variables in state if not found in var_dict
                    input_data[key] = safe_format(value['value'], state)
                except KeyError as no_var_exception:
                    logger.error(f"KeyError in fstring formatting for key '{key}' with state data.\n{no_var_exception}")
                    # leave value as is if still not found (could be a constant string marked as fstring by mistake)
                    input_data[key] = value['value']
        elif value['type'] == 'fixed':
            input_data[key] = value['value']
        else:
            input_data[key] = source.get(value['value'], "")
    return input_data

def safe_format(template, mapping):
    """Format a template string using a mapping, leaving placeholders unchanged if keys are missing."""

    def replacer(match):
        key = match.group(1)
        return str(mapping.get(key, f'{{{key}}}'))
    return re.sub(r'\{(\w+)\}', replacer, template)

def create_pydantic_model(model_name: str, variables: dict[str, dict]):
    fields = {}
    for var_name, var_data in variables.items():
        fields[var_name] = (parse_type(var_data['type']), Field(description=var_data.get('description', None)))
    return create_model(model_name, **fields)