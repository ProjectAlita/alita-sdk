from langchain.tools import BaseTool
from typing import Any, Type
from pydantic import create_model, validator, BaseModel
from pydantic.fields import FieldInfo

applicationToolSchema = create_model(
    "applicatrionSchema", 
    task = (str, FieldInfo(description="Task for Application")), 
    chat_history = (str, FieldInfo(description="Chat History relevant for Application"))
)

class Application(BaseTool):
    name: str
    description: str
    appliacation: Any
    args_schema: Type[BaseModel] = applicationToolSchema
    
    @validator('name', pre=True, allow_reuse=True)
    def remove_spaces(cls, v):
        return v.replace(' ', '')
    
    def _run(self, task, chat_history):
        if isinstance(chat_history, list):
            chat_history.append({"content": task, "role": "user"})
        else:
            chat_history = [{"content": task, "role": "user"}]
        response = self.appliacation.invoke({"content": task, "chat_history": chat_history})
        return response["output"]
    
