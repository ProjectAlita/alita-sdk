from typing import List, Optional, Literal
from elitea_analyse.ado.azure_search import AzureSearch
from pydantic import SecretStr, create_model, BaseModel, ConfigDict, Field

from langchain_core.tools import BaseTool, BaseToolkit

from alita_sdk.tools.utils import get_max_toolkit_length
from alita_sdk.tools.base.tool import BaseAction
from alita_sdk.runtime.clients.client import AlitaClient  # Add this import at the top of the file
from alita_sdk.runtime.tools.artifact import ArtifactWrapper
from .api_wrapper import AdoAnalyseWrapper

from ...utils import check_schema


name = "Analyse_Ado"


class AnalyseAdo(BaseToolkit):
    tools: List[BaseTool] = []
    toolkit_max_length: int = 0

    @staticmethod
    def toolkit_config_schema() -> type[BaseModel]:
        selected_tools = {
            x["name"]: x["args_schema"].schema()
            for x in AdoAnalyseWrapper.model_construct().get_available_tools()
        }
        AnalyseAdo.toolkit_max_length = get_max_toolkit_length(selected_tools)

        return create_model(
            "analyse_ado",
            organization=(str, Field(description="Azure DevOps organization name",
                json_schema_extra={"toolkit_name": True, "max_toolkit_length": AnalyseAdo.toolkit_max_length})),
            username=(str, Field(description="Azure DevOps username (e.g., 'john.doe@domain.com')")),
            token=(SecretStr, Field(description="Azure DevOps Access Token", json_schema_extra={"secret": True})),
            project_keys=(Optional[str], Field(description="Azure DevOps project keys separated by comma", default=None)),
            default_branch_name=(Optional[str], Field(description="Default branch name", default="main")),
            area=(Optional[str], Field(description="Area path filter", default="")),
            artifact_bucket_path=(Optional[str], Field(description="Artifact Bucket Path", default="analyse-ado")),
            selected_tools=(List[Literal[tuple(selected_tools)]], Field(default=[], json_schema_extra={"args_schemas": selected_tools})),
            __config__=ConfigDict(json_schema_extra={"metadata": {
                    "label": "Analyse_Ado",
                    "icon_url": "ado-icon.svg", # ???
                    "hidden": True,
                    "sections": {
                        "auth": {
                            "required": True,
                            "subsections": [{"name": "Token", "fields": ["token"]}],
                        }
                    },
                }
            })
        )
    
    @classmethod
    def get_toolkit(cls, client: "AlitaClient", selected_tools: list[str], **kwargs):

        bucket_path = kwargs.get("artifact_bucket_path") or "analyse-ado"
        artifact_wrapper = ArtifactWrapper(client=client, bucket=bucket_path)
        check_schema(artifact_wrapper)

        project_keys = kwargs.get("project_keys") or ""
        area = kwargs.get("area", "")

        organization = kwargs.get("organization")
        username = kwargs.get("username")
        token = kwargs.get("token")

        if not organization or not username or not token:
            raise ValueError("Organization, username, and token must be provided.")

        ado_search = AzureSearch(organization=organization, user=username, token=token)

        ado_analyse_wrapper = AdoAnalyseWrapper(
            artifacts_wrapper=artifact_wrapper,
            project_keys=project_keys,
            default_branch_name=kwargs.get("default_branch_name", "main"),
            area=area,
            ado_search=ado_search,
        )

        selected_tools = selected_tools or []
        available_tools = ado_analyse_wrapper.get_available_tools()

        tools = []
        for tool in available_tools:
            if selected_tools:
                if tool["name"] not in selected_tools:
                    continue
            tools.append(
                BaseAction(
                    api_wrapper=ado_analyse_wrapper,
                    name=tool["name"],
                    description=tool["description"],
                    args_schema=tool["args_schema"],
                )
            )

        return cls(tools=tools)

    def get_tools(self):
        return self.tools
