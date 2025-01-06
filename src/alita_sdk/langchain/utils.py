import builtins
import json
import logging
import re
from pydantic import create_model, Field
from typing import Tuple, TypedDict, Any, Optional, Annotated
from langchain_core.messages import AnyMessage
from langchain_core.prompts import PromptTemplate
from langgraph.graph import MessagesState, add_messages

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
        return eval(type_str, {**vars(builtins), **globals()})
    except Exception as e:
        print(f"Error parsing type: {e}")
        return Any


def create_state(data: Optional[dict] = None):
    state_dict = {'input': str,}
    if not data:
        data = {'messages': 'list[str]'}
    for key, value in data.items():
        if key == 'messages':
            state_dict[key] = Annotated[list[AnyMessage], add_messages]
        elif value in ['str', 'int', 'float', 'bool', 'list', 'dict']:
            state_dict[key] = parse_type(value)
    return TypedDict('State', state_dict)

def create_typed_dict_from_yaml(data):
    # Extract class name and attributes
    class_name, attributes = next(iter(data.items()))

    # Create a TypedDict class
    cls = TypedDict(class_name, {attr: parse_type(attr_type) for attr, attr_type in attributes.items()})
    
    return cls

def propagate_the_input_mapping(input_mapping: dict[str, dict], input_variables: list[str], state: dict) -> dict:
    input_data = {}
    for key, value in input_mapping.items():
        if key == 'chat_history':
            input_data[key] = state.get('messages', [])
        elif value['type'] == 'fstring':
            var_dict = {var: state.get(var, "") for var in input_variables}
            input_data[key] = PromptTemplate.from_template(value['value']).partial(**var_dict).format(**var_dict)
        elif value['type'] == 'fixed':
            input_data[key] = value['value']
        else:
            input_data[key] = state.get(value['value'], "")
    return input_data


def create_pydantic_model(model_name: str, variables: dict[str, dict]):
    fields = {}
    for var_name, var_data in variables.items():
        fields[var_name] = (parse_type(var_data['type']), Field(description=var_data.get('description', None)))
    return create_model(model_name, **fields)