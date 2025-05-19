import json
from typing import List, Optional, Literal
from pydantic import create_model, BaseModel, ConfigDict, Field

from langchain_core.tools import BaseTool, BaseToolkit

from elitea_analyse.jira.jira_connect import connect_to_jira
from alita_tools.base.tool import BaseAction

from ....tools.artifact import ArtifactWrapper
from .api_wrapper import JiraAnalyseWrapper

from ...utils import check_schema

name = "Analyse_Jira"

class AnalyseJira(BaseToolkit):
    tools: List[BaseTool] = []

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        return create_model(
            "analyse_jira",
            project_keys = (str, Field(description="Jira project keys separated by comma")),
            team_field = (str, Field(description="Jira field used as identifier for team")),
            environment_field = (str, Field(description="Jira field used as identifier for environment")),
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
            client=client, bucket=kwargs.get('artifact_bucket_path')
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
        jira_custom_files['team'] = kwargs.get('team_field', '')
        jira_custom_files['environment'] = kwargs.get('environment_field', '')
        closed_status = kwargs.get('closed_status', '')
        defects_name = kwargs.get('defects_name', '')

        jira_credentials = {  
            "username": jira_username,
            "base_url": jira_base_url,
            "token": jira_token,
            "api_key": jira_api_key,
            "verify_ssl": jira_verify_ssl
        }

        jira = connect_to_jira(credentials=jira_credentials)
        if not jira:
            raise ValueError(
                "Failed to connect to Jira. Please check your credentials."
            )

        api_wrapper = JiraAnalyseWrapper(
            artifacts_wrapper=artifact_wrapper,
            jira=jira,
            closed_status=closed_status,
            defects_name=defects_name,
            custom_fields=jira_custom_files,
        )
        tools = []
        available_tools = api_wrapper.get_available_tools()
        for tool in available_tools:
            tools.append(
                BaseAction(
                    api_wrapper=api_wrapper,
                    name=tool["name"],
                    description=tool["description"],
                    args_schema=tool["args_schema"],
                )
            )

        return cls(tools=tools)

    def get_tools(self):
        return self.tools
