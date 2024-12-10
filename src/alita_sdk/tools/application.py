from ..utils.utils import clean_string
from json import dumps
from langchain_core.tools import BaseTool
from langchain_core.messages import BaseMessage, AIMessage
from typing import Any, Type, Optional
from pydantic import create_model, field_validator, BaseModel
from pydantic.fields import FieldInfo
from ..langchain.mixedAgentRenderes import convert_message_to_json
from logging import getLogger
logger = getLogger(__name__)

applicationToolSchema = create_model(
    "applicatrionSchema", 
    task = (str, FieldInfo(description="Task for Application")), 
    chat_history = (Optional[list], FieldInfo(description="Chat History relevant for Application", default=[]))
)

def formulate_query(args, kwargs):
    chat_history = []
    if kwargs.get('chat_history'):
        if isinstance(kwargs.get('chat_history')[-1], BaseMessage):
            chat_history = convert_message_to_json(kwargs.get('chat_history')[:])
        elif isinstance(kwargs.get('chat_history')[-1], dict):
            chat_history = kwargs.get('chat_history')[:]
        elif isinstance(kwargs.get('chat_history')[-1], str):
            chat_history = []
            for each in kwargs.get('chat_history')[:]:
                chat_history.append(AIMessage(each))
    return {"input": kwargs.get('task'), "chat_history": chat_history}
    
    

class Application(BaseTool):
    name: str
    description: str
    application: Any
    args_schema: Type[BaseModel] = applicationToolSchema
    return_type: str = "str"
    
    @field_validator('name', mode='before')
    @classmethod
    def remove_spaces(cls, v):
        return clean_string(v)
        
    
    def _run(self, *args, **kwargs):
        response = self.application.invoke(formulate_query(args, kwargs))
        if self.return_type == "str":
            return response["output"]
        else:
            return {"messages": [{"role": "assistant", "content": response["output"]}]}
    
