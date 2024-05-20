from typing import List, Any
from langchain_community.agent_toolkits.base import BaseToolkit
from langchain_core.tools import BaseTool
from ..tools.application import Application, applicationToolSchema

class ApplicationToolkit(BaseToolkit):
    tools: List[BaseTool] = []
    
    @classmethod
    def get_toolkit(cls, client: Any, application_id: int, application_version_id: int, app_api_key: str, selected_tools: list[str] = [] ):
        from ..llms.alita import AlitaChatModel
        
        
        app_details = client.get_app_details(application_id)
        version_details = client.get_app_version_details(application_id, application_version_id)
        settings = {
            "deployment": "https://eye.projectalita.ai",
            "model": "gpt-4-0125-preview",
            "api_key": app_api_key,
            "project_id": client.project_id,
            "integration_uid": version_details['llm_settings']['integration_uid'],
            "max_tokens": version_details['llm_settings']['max_tokens'],
            "top_p": version_details['llm_settings']['top_p'],
            "top_k": version_details['llm_settings']['top_k'],
            "temperature": version_details['llm_settings']['temperature'],
        }

        app = client.application(AlitaChatModel(**settings), application_id, application_version_id)
        return cls(tools=[Application(name=app_details.get("name"), description=app_details.get("description"), appliacation=app, args_schema=applicationToolSchema)])
            
    def get_tools(self):
        return self.tools
    