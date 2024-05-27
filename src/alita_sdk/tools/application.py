from langchain.tools import BaseTool
from langchain.pydantic_v1 import BaseModel, Field
from typing import Any
from pydantic import create_model
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
    
    def _run(self, task, chat_history):
        if isinstance(chat_history, list):
            chat_history.append({"content": task, "role": "user"})
        else:
            chat_history = [{"content": task, "role": "user"}]
        response = self.appliacation.invoke({"content": task, "chat_history": chat_history})
        return response["output"]
    
