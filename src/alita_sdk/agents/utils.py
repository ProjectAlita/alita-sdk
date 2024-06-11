import logging
import json
import re

logger = logging.getLogger(__name__)



def extract_using_regex(text):
    # Extracting the thoughts section
    try:
        thoughts_text = re.search(r'"text": "(.*?)",', text, re.DOTALL).group(1)
    except AttributeError:
        thoughts_text = None
    try:
        thoughts_plan = re.search(r'"plan": "(.*?)",', text, re.DOTALL).group(1)
    except AttributeError:
        thoughts_plan = None
    try:
        thoughts_criticism = re.search(r'"criticism": "(.*?)"\s*},', text, re.DOTALL).group(1)
    except AttributeError:
        thoughts_criticism = None

    # Extracting the tool section
    args_dict = {}
    try:
        tool_name = re.search(r'"name": "(.*?)"', text, re.DOTALL).group(1)
        # Parsing the args JSON string to dict
        args_block_match = re.search(r'"args":\s*{(.+?)}\s*}', text, re.DOTALL)
        args_dict = {}
        if args_block_match:
            args_block = args_block_match.group(1)
            keys = [match.group(1) for match in re.finditer(r'"(\w+)":', args_block)]
            for key in keys:
                args_pattern = r'"'+key+'":\s*"(.*?)"(?=,?|$)'
                args_matches = re.findall(args_pattern, args_block, re.DOTALL)
                for value in args_matches:
                    # Here you could handle specific parsing logic for each key if necessary
                    args_dict[key] = value.replace('\\n', '\n')  # Convert escaped newlines back to actual newlines if needed  
    except AttributeError:
        tool_name = None
    # Constructing result dictionary
    result = {
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
    return result


def unpack_json(json_data: str | dict, message_key=None):
    if isinstance(json_data, str):
        try:
            if '```json' in json_data:
                pattern = r'```json(.*)```'
                matches = re.findall(pattern, json_data, re.DOTALL)
                if matches:
                    text = json_data.replace(f'{matches[0]}', '').replace('```json', '').replace('```', '').strip()
                    res = json.loads(matches[0])
                    if message_key and text:
                        txt = "\n".join([match.value for match in message_key.find(res)])
                        message_key.update(res, txt + text)
                    return res
            elif json_data.strip().startswith("{") and json_data.strip().endswith("}"):
                return json.loads(json_data)
            else:
                match = re.search(r"\{.*\}", json_data, re.DOTALL)
                if match:
                    return json.loads(match.group(0))
                else:
                    raise IndexError("No match found")
        except (json.decoder.JSONDecodeError, IndexError) as e:
            json_data = extract_using_regex(json_data)
            if json_data.get('thoughts', {}).get("text", None) or json_data.get('tool', {}).get("name", None):
                return json_data
            else:
                logger.error(f"Error in unpacking json with regex: {json_data}")
                raise e
    elif isinstance(json_data, dict):
        return json_data
    else:
        raise ValueError("Wrong type of json_data")
