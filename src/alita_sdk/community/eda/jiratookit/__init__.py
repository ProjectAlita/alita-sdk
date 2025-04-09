import os
import json
from typing import List, Optional, Literal
from pydantic import create_model, BaseModel, ConfigDict, Field

from langchain_core.tools import BaseTool, BaseToolkit
from ....tools.artifact import ArtifactWrapper
from .api_wrapper import EDAApiWrapper
from ...utils import check_schema
from ..jira.jira_connect import connect_to_jira
import shutil

name = "Analyse_Jira"

class AnalyseJira(BaseToolkit):
    tools: List[BaseTool] = []
    
    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        return create_model(
            "analyse_jira",
            project_keys = (str, Field(description="Jira project keys separated by comma")),
            team_filed = (str, Field(description="Jira filed used as identifier for team")),
            envoironment_field = (str, Field(description="Jira filed used as identifier for environment")),
            defects_name = (str, Field(description="Jira defects type")),
            closed_status = (str, Field(description="Jira closed statuse")),
            jira_base_url=(str, Field(description="Jira URL")),
            jira_cloud=(bool, Field(description="Hosting Option")),
            jira_api_key=(Optional[str], Field(description="API key", default=None, json_schema_extra={'secret': True})),
            jira_username=(Optional[str], Field(description="Jira Username", default=None)),
            jira_token=(Optional[str], Field(description="Jira token", default=None, json_schema_extra={'secret': True})),
            jira_verify_ssl=(bool, Field(description="Verify SSL", default=True)),
            jira_custom_files=(Optional[str], Field(description="Additional fields", default="")),
            jira_api_version=(str, Field(description="Jira API Version", default="2")),
            artifact_bucket_path=(str, Field(description="Artifact Bucket Path")),
            __config__=ConfigDict(json_schema_extra={'metadata': {"label": "Analyse_Jira", "icon_url": None, "hidden": True}})
        )

    @classmethod
    def get_toolkit(cls, client: 'AlitaClient', **kwargs):
        artifact_wrapper = ArtifactWrapper(
            client=client, bucket_path=kwargs.get('artifact_bucket_path')
        )
        check_schema(artifact_wrapper)
        
        # artifacts_wrapper: ArtifactWrapper
        # jira: JIRA
        # closed_status: str # Jira ticket closed statuses
        # defects_name: str # Jira ticket defects name
        # custom_fields: dict # Jira ticket custom fields
        
        jira_base_url = kwargs.get('jira_base_url')
        jira_verify_ssl = kwargs.get('jira_verify_ssl')
        jira_username = kwargs.get('jira_username')
        jira_token = kwargs.get('jira_token')
        jira_api_key = kwargs.get('jira_api_key')
        try:
            jira_custom_files = json.loads(kwargs.get('jira_custom_files', '{}'))
        except:
            jira_custom_files = {}
        jira_custom_files['team'] = kwargs.get('team_filed')
        jira_custom_files['envoironment'] = kwargs.get('envoironment_field')
        closed_status = kwargs.get('closed_status')
        defects_name = kwargs.get('defects_name')
        #TODO: we need to remove this in favor of IOStreams, currently it is here for backward compatibility
        if not os.path.exists('raw_data'):
            os.makedirs('raw_data')
        else:
            shutil.rmtree('raw_data')
            os.makedirs('raw_data')
            
        api_wrapper = EDAApiWrapper(
            artifact_wrapper=artifact_wrapper,
            jira=connect_to_jira(jira_base_url=jira_base_url, jira_username=jira_username, 
                                 jira_token=jira_token, jira_api_key=jira_api_key, 
                                 jira_verify_ssl=jira_verify_ssl),
            closed_status=closed_status,
            defects_name=defects_name,
            custom_fields = jira_custom_files
        )

        tools = api_wrapper.get_available_tools()
        return cls(tools=tools)

    def get_tools(self):
        return self.tools
