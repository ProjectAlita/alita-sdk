import logging
import json
import re

logger = logging.getLogger(__name__)


def unpack_json(json_data: str | dict, message_key=None):
    if isinstance(json_data, str):
        if '```json' in json_data:
            pattern = r'```json(.*)```'
            matches = re.findall(pattern, json_data, re.DOTALL)
            try:
                text = json_data.replace(f'{matches[0]}', '').replace('```json', '').replace('```', '').strip()
                res = json.loads(matches[0])
                if message_key and text:
                    txt = "\n".join([match.value for match in message_key.find(res)])
                    message_key.update(res, txt + text)
                return res
            except IndexError:
                logger.error(f"Error in unpacking json: {json_data}")
                raise ValueError("Wrong type of json_data")
        try:
            return json.loads(json_data)
        except json.decoder.JSONDecodeError as e:
            logger.error(f"Error in unpacking json: {json_data}")
            raise e
    elif isinstance(json_data, dict):
        return json_data
    else:
        raise ValueError("Wrong type of json_data")
