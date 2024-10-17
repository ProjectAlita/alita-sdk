from ..utils.utils import clean_string
from json import dumps
from langchain_core.tools import BaseTool
from langchain_core.messages import BaseMessage, AIMessage
from typing import Any, Type, Dict
from pydantic import create_model, validator, BaseModel
from pydantic.fields import FieldInfo
from ..agents.mixedAgentRenderes import convert_message_to_json

applicationToolSchema = create_model(
    "applicatrionSchema", 
    task = (str, FieldInfo(description="Task for Application")), 
    chat_history = (str, FieldInfo(description="Chat History relevant for Application"))
)

applicationWFSchema = create_model(
    "applicatrionSchema", 
    messages = (list, FieldInfo(description="conversation"))
)

def formulate_query(args, kwargs):
    print(kwargs)
    if kwargs.get('messages'):
        if isinstance(kwargs.get('messages')[-1], BaseMessage):
            task = kwargs.get('messages')[-1].content
            chat_history = convert_message_to_json(kwargs.get('messages')[:-1])
        elif isinstance(kwargs.get('messages')[-1], dict):
            task = kwargs.get('messages')[-1]['content']
            chat_history = kwargs.get('messages')[:-1]
        elif isinstance(kwargs.get('messages')[-1], str):
            task = kwargs.get('messages')[-1]
            chat_history = []
            for each in kwargs.get('messages')[:-1]:
                chat_history.append(AIMessage(each))
        return {"input": task, "chat_history": chat_history}
    else:
        task = kwargs.get('task')
        chat_history = kwargs.get('chat_history', '')        
        if chat_history:
            task = "Task: " + task + "\nAdditional context: " + chat_history
        return {"input": task, "chat_history": []}
    

class Application(BaseTool):
    name: str
    description: str
    application: Any
    args_schema: Type[BaseModel] = applicationToolSchema
    return_type: str = "str"
    
    @validator('name', pre=True, allow_reuse=True)
    def remove_spaces(cls, v):
        return clean_string(v)
        
    
    def _run(self, *args, **kwargs):
        response = self.application.invoke(formulate_query(args, kwargs))
        if self.return_type == "str":
            return response["output"]
        else:
            return {"messages": [{"role": "assistant", "content": response["output"]}]}
    
