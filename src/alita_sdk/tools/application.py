from langchain_core.tools import BaseTool
from typing import Any, Type
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
    task = kwargs.get('task') if kwargs.get('task') else kwargs.get('messages')[-1].content
    chat_history = kwargs.get('chat_history', convert_message_to_json(kwargs.get('messages', [])[:-1]))
    return {"input": task, "chat_history": chat_history}

class Application(BaseTool):
    name: str
    description: str
    appliacation: Any
    args_schema: Type[BaseModel] = applicationToolSchema
    return_type: str = "str"
    
    @validator('name', pre=True, allow_reuse=True)
    def remove_spaces(cls, v):
        return v.replace(' ', '')
    
    def _run(self, *args, **kwargs):
        response = self.appliacation.invoke(formulate_query(args, kwargs))
        if self.return_type == "str":
            return response["output"]
        else:
            return {"messages": [{"role": "assistant", "content": response["output"]}]}
    
