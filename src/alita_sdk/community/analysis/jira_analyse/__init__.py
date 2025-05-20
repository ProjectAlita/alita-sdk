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
    def toolkit_config_schema() -> type[BaseModel]:
        return create_model(
            "analyse_jira",
            jira_base_url=(str, Field(description="Jira URL")),
            jira_cloud=(bool, Field(description="Hosting Option")),
            jira_username=(str, Field(description="Jira Username")),
            jira_api_key=(Optional[str], Field(description="API key", json_schema_extra={'secret': True}, default="")),
            jira_token=(Optional[str], Field(description="Jira token", json_schema_extra={'secret': True}, default="")),
            # TODO: Add these fields to the schema as custom fields comma-separated if required
            team_field=(Optional[str], Field(description="Jira field used as identifier for team", default="")),
            environment_field=(Optional[str], Field(description="Jira field used as identifier for environment", default="")),
            defects_name=(Optional[str], Field(description="Jira defects type", default="")),
            closed_status=(Optional[str], Field(description="Jira closed status", default="")),
            jira_verify_ssl=(bool, Field(description="Verify SSL")),
            jira_custom_fields=(Optional[str], Field(description="Additional fields, split by comma", default="")),
            artifact_bucket_path=(Optional[str], Field(description="Artifact Bucket Path", default="")),
            __config__=ConfigDict(json_schema_extra={'metadata':
                {
                    "label": "Analyse_Jira",
                    "icon_url": "jira-icon.svg",
                    "hidden": False,
                    "sections": {
                        "auth": {
                            "required": True,
                            "subsections": [
                                {
                                    "name": "Api key",
                                    "fields": ["jira_api_key"]
                                },
                                {
                                    "name": "Token",
                                    "fields": ["jira_token"]
                                }
                            ]
                        }
                    }
                }
            })
        )

    @classmethod
    def get_toolkit(cls, client: 'AlitaClient', **kwargs):
        bucket_path = kwargs.get('artifact_bucket_path') or 'analyse-jira'
        artifact_wrapper = ArtifactWrapper(
            client=client, bucket=bucket_path
        )
        check_schema(artifact_wrapper)

        jira_base_url = kwargs.get('jira_base_url')
        jira_verify_ssl = kwargs.get('jira_verify_ssl')
        jira_username = kwargs.get('jira_username')
        jira_token = kwargs.get('jira_token')
        jira_api_key = kwargs.get('jira_api_key')
        try:
            jira_custom_fields = json.loads(kwargs.get('jira_custom_fields', '{}'))
        except:
            jira_custom_fields = {}
        jira_custom_fields['team'] = kwargs.get('team_field', '')
        jira_custom_fields['environment'] = kwargs.get('environment_field', '')
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
            custom_fields=jira_custom_fields,
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
