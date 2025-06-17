from typing import List, Any
from pydantic import create_model, BaseModel
from pydantic.fields import FieldInfo
from langchain_community.agent_toolkits.base import BaseToolkit
from langchain_core.tools import BaseTool
from ..tools.prompt import Prompt

class PromptToolkit(BaseToolkit):
    tools: List[BaseTool] = []
    
    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        return create_model(
            "prompt",
            # client = (Any, FieldInfo(description="Client object", required=True, autopopulate=True)),
            prompts = (list, FieldInfo(description="List of lists for [[prompt_id, prompt_version_id]]"))
        )
    
    @classmethod
    def get_toolkit(cls, client: Any, prompts: list[list[int, int]]):
        tools = []
        for prompt_config in prompts:
            prmt = client.prompt(prompt_config[0], prompt_config[1], return_tool=True)
            tools.append(Prompt(
                name=prmt.name, description=prmt.description, 
                prompt=prmt, args_schema=prmt.create_pydantic_model(),
                return_type='str'))
        return cls(tools=tools)
            
    def get_tools(self):
        return self.tools