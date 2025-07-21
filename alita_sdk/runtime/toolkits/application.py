from typing import List, Any, Optional

from langgraph.store.base import BaseStore
from pydantic import create_model, BaseModel, Field
from langchain_community.agent_toolkits.base import BaseToolkit
from langchain_core.tools import BaseTool
from ..tools.application import Application, applicationToolSchema

class ApplicationToolkit(BaseToolkit):
    tools: List[BaseTool] = []
    
    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        return create_model(
            "application",
            # client = (Any, FieldInfo(description="Client object", required=True, autopopulate=True)),

            application_id = (int, Field(description="Application id")),
            application_version_id = (int, Field(description="Application version id")),
            app_api_key = (Optional[str], Field(description="Application API Key", autopopulate=True, default=None))
        )
    
    @classmethod
    def get_toolkit(cls, client: 'AlitaClient', application_id: int, application_version_id: int,
                    selected_tools: list[str] = [], store: Optional[BaseStore] = None):
        
        app_details = client.get_app_details(application_id)
        version_details = client.get_app_version_details(application_id, application_version_id)
        model_settings = {
            "max_tokens": version_details['llm_settings']['max_tokens'],
            "top_p": version_details['llm_settings']['top_p'],
            "temperature": version_details['llm_settings']['temperature'],
        }

        app = client.application(application_id, application_version_id, store=store, 
                                 llm=client.get_llm(version_details['llm_settings']['model_name'], 
                                                    model_settings))
        return cls(tools=[Application(name=app_details.get("name"), 
                                      description=app_details.get("description"), 
                                      application=app, 
                                      args_schema=applicationToolSchema,
                                      return_type='str')])
            
    def get_tools(self):
        return self.tools
    