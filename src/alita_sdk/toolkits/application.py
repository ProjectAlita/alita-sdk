from typing import List, Any
from pydantic import create_model, BaseModel
from pydantic.fields import FieldInfo
from langchain_community.agent_toolkits.base import BaseToolkit
from langchain_core.tools import BaseTool
from ..tools.application import Application, applicationToolSchema, applicationWFSchema

class ApplicationToolkit(BaseToolkit):
    tools: List[BaseTool] = []
    
    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        return create_model(
            "application",
            client = (Any, FieldInfo(description="Client object", required=True, autopopulate=True)),
            application_id = (int, FieldInfo(description="Application id")),
            application_version_id = (int, FieldInfo(description="Application version id")),
            app_api_key = (str, FieldInfo(description="Application API Key", autopopulate=True)),
            is_workflow = (bool, FieldInfo(description="Is this a workflow", default=False, required=False, autopopulate=True))
        )
    
    @classmethod
    def get_toolkit(cls, client: Any, application_id: int, application_version_id: int, app_api_key: str, 
                    selected_tools: list[str] = [], is_workflow: bool=False):
        from ..llms.alita import AlitaChatModel
        
        app_details = client.get_app_details(application_id)
        version_details = client.get_app_version_details(application_id, application_version_id)
        settings = {
            "deployment": client.base_url,
            "model": version_details['llm_settings']['model_name'],
            "api_key": app_api_key,
            "project_id": client.project_id,
            "integration_uid": version_details['llm_settings']['integration_uid'],
            "max_tokens": version_details['llm_settings']['max_tokens'],
            "top_p": version_details['llm_settings']['top_p'],
            "top_k": version_details['llm_settings']['top_k'],
            "temperature": version_details['llm_settings']['temperature'],
        }

        app = client.application(AlitaChatModel(**settings), application_id, application_version_id)
        return cls(tools=[Application(name=app_details.get("name"), 
                                      description=app_details.get("description"), 
                                      application=app, 
                                      args_schema=applicationWFSchema if is_workflow else applicationToolSchema,
                                      return_type='dict' if is_workflow else 'str')])
            
    def get_tools(self):
        return self.tools
    