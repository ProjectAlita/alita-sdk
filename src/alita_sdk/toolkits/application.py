from typing import List, Any
from langchain_community.agent_toolkits.base import BaseToolkit
from langchain_core.tools import BaseTool
from ..tools.application import Application, applicationToolSchema

class ApplicationToolkit(BaseToolkit):
    tools: List[BaseTool] = []
    
    @classmethod
    def get_toolkit(cls, client: Any, application_id: list[int], application_version_id: list[int], selected_tools: list[str] = [] ):
        app_details = client.get_app_details(application_id)
        app = client.application(application_id, application_version_id)
        return cls(tools=[Application(name=app_details.get("name"), description=app_details.get("description"), appliacation=app, args_schema=applicationToolSchema)])
            
    def get_tools(self):
        return self.tools
    