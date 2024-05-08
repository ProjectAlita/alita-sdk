from langchain.tools import BaseTool
from langchain.pydantic_v1 import BaseModel, Field
from typing import Any
from langchain.pydantic_v1 import create_model

applicationToolSchema = create_model("applicatrionSchema", task = (str, None), chat_history = (str, None))

class Application(BaseTool):
    name: str
    description: str
    appliacation: Any
    
    def _run(self, task, chat_history):
        response = self.appliacation.invoke({"content": task, "chat_history": chat_history})
        return response["output"]
    
