from typing import List, Optional, Literal
from pydantic import SecretStr, create_model, BaseModel, ConfigDict, Field

from langchain_core.tools import BaseTool, BaseToolkit

from elitea_analyse.github.github_org import GitHubGetOrgLvl
from alita_sdk.runtime.clients.client import AlitaClient 
from alita_sdk.tools.utils import get_max_toolkit_length
from alita_sdk.tools.base.tool import BaseAction

from alita_sdk.runtime.tools.artifact import ArtifactWrapper
from .api_wrapper import GitHubAnalyseWrapper

from ...utils import check_schema


name = "Analyse_Github"


class AnalyseGithub(BaseToolkit):
    tools: List[BaseTool] = []
    toolkit_max_length: int = 0

    @staticmethod
    def toolkit_config_schema() -> type[BaseModel]:
        selected_tools = {
            x["name"]: x["args_schema"].schema()
            for x in GitHubAnalyseWrapper.model_construct().get_available_tools()
        }
        AnalyseGithub.toolkit_max_length = get_max_toolkit_length(selected_tools)

        return create_model(
            "analyse_github",  
            owner=(str, Field(description="GitHub owner name",
                json_schema_extra={"toolkit_name": True, "max_toolkit_length": AnalyseGithub.toolkit_max_length})),
            token=(SecretStr, Field(description="Github Access Token", json_schema_extra={"secret": True})),
            repos=(Optional[str],
                Field(description="Comma-separated list of GitHub repository names e.g. 'repo1,repo2'", default=None)),
            artifact_bucket_path=(Optional[str],
                                  Field(description="Artifact Bucket Path", default="analyse-github")),
            selected_tools=(
                List[Literal[tuple(selected_tools)]], Field(default=[],
                json_schema_extra={"args_schemas": selected_tools})
            ),
            __config__=ConfigDict(json_schema_extra={"metadata": {
                    "label": "Analyse_Github",
                    "icon_url": None, # ?? is exists
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
        bucket_path = kwargs.get("artifact_bucket_path") or "analyse-github"
        artifact_wrapper = ArtifactWrapper(client=client, bucket=bucket_path)
        check_schema(artifact_wrapper)

        owner = kwargs.get("owner")
        token = kwargs.get("token")

        if not owner or not token:
            raise ValueError("GitHub owner and token must be provided.")

        git = GitHubGetOrgLvl(owner=owner, token=token)

        github_analyse_wrapper = GitHubAnalyseWrapper(
            artifacts_wrapper=artifact_wrapper,
            repos=kwargs.get("repos") or "",
            git=git
        )

        selected_tools = selected_tools or []
        available_tools = github_analyse_wrapper.get_available_tools()

        tools = []
        for tool in available_tools:
            if selected_tools and tool["name"] not in selected_tools:
                continue
            tools.append(
                BaseAction(
                    api_wrapper=github_analyse_wrapper,
                    name=tool["name"],
                    description=tool["description"],
                    args_schema=tool["args_schema"],
                )
            )

        return cls(tools=tools)

    def get_tools(self):
        return self.tools
