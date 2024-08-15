from langchain_core.tools import BaseTool
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
        response = self.appliacation.invoke({"input": task, "chat_history": chat_history})
        return response["output"]
    
