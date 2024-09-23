from traceback import format_exc
from typing import List, Dict
from abc import ABCMeta
from jinja2 import Environment, TemplateSyntaxError, UndefinedError
import logging
from langgraph.graph import END

logger = logging.getLogger(__name__)

class TransformationError(Exception):
    "Raised when transformation fails"


class MyABC(ABCMeta):
    meta_registry = {}

    def __new__(mcs, name, bases, attrs):
        resulting_class = super().__new__(mcs, name, bases, attrs)
        if bases:  # exlcuding parent class
            name = name.split('TransformerEvaluate')[0].lower()
            mcs.meta_registry[name] = resulting_class
            resulting_class._output_format = name
        return resulting_class


class EvaluateTemplate(metaclass=MyABC):
    def __init__(self, query: str,  chat_history: str, last_message: str):
        self.query = query
        self.chat_history = chat_history
        self.last_message = last_message

    def extract(self):
        environment = Environment()

        def json_loads_filter(json_string: str,do_replace: bool = False):
            import json
            if do_replace:
                json_string = json_string.replace("'", "\"")
            return json.loads(json_string)

        environment.filters['json_loads'] = json_loads_filter
        try:
            template = environment.from_string(self.query)
            print("Last message: ", self.last_message)
            print(self.chat_history)
            result = template.render(chat_history=self.chat_history, last_message=self.last_message)
            print(result)
        except (TemplateSyntaxError, UndefinedError):
            logger.critical(format_exc())
            logger.info('Template str: %s', self.query)
            raise Exception("Invalid jinja template in context")
        return result
        
    # template method
    def evaluate(self):
        # extracting
        value: List[Dict] = self.extract()
        if 'END' in value.strip():
            return END
        else:
            return value.strip()