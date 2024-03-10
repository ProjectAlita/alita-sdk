
import json
import re

def unpack_json(json_data, message_key=None):
    if (isinstance(json_data, str)):
        if '```json' in json_data:
            pattern = r'```json(.*)```'
            matches = re.findall(pattern, json_data, re.DOTALL)
            text = json_data.replace(f'{matches[0]}', '').replace('```json', '').replace('```', '').strip()
            res = json.loads(matches[0])
            if message_key and text:
                txt = "\n".join([match.value for match in message_key.find(res)])
                message_key.update(res, txt + text)
            return res
        return json.loads(json_data)
    elif (isinstance(json_data, dict)):
        return json_data
    else:
        raise ValueError("Wrong type of json_data")