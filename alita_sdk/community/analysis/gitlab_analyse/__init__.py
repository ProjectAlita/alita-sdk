from typing import List, Optional, Literal
from elitea_analyse.git.git_search import GitLabV4Search
from pydantic import SecretStr, create_model, BaseModel, ConfigDict, Field

from langchain_core.tools import BaseTool, BaseToolkit

from alita_sdk.tools.utils import get_max_toolkit_length
from alita_sdk.tools.base.tool import BaseAction
from alita_sdk.runtime.clients.client import AlitaClient 
from alita_sdk.runtime.tools.artifact import ArtifactWrapper
from .api_wrapper import GitLabAnalyseWrapper

from ...utils import check_schema


name = "Analyse_GitLab"


class AnalyseGitLab(BaseToolkit):
    tools: List[BaseTool] = []
    toolkit_max_length: int = 0

    @staticmethod
    def toolkit_config_schema() -> type[BaseModel]:
        selected_tools = {
            x["name"]: x["args_schema"].schema()
            for x in GitLabAnalyseWrapper.model_construct().get_available_tools()
        }
        AnalyseGitLab.toolkit_max_length = get_max_toolkit_length(selected_tools)

        return create_model(
            "analyse_gitlab",
            url=(
                str,
                Field(
                    description="GitLab URL (e.g., git.epam.com)",
                    json_schema_extra={"toolkit_name": True, "max_toolkit_length": AnalyseGitLab.toolkit_max_length}
                )
            ),
            project_ids=(Optional[str], Field(description="GitLab project ids separated by comma", default=None)),
            jira_project_keys=(Optional[str],
                               Field(description="GitLab project Jira keys separated by comma", default=None)),
            token=(SecretStr, Field(description="GitLab Personal Access Token", json_schema_extra={"secret": True})),
            default_branch_name=(Optional[str], Field(description="Default branch name", default="master")),
            artifact_bucket_path=(Optional[str], Field(description="Artifact Bucket Path", default="analyse-gitlab")),
            selected_tools=(
                List[Literal[tuple(selected_tools)]],
                Field(default=[], json_schema_extra={"args_schemas": selected_tools})
            ),
            __config__=ConfigDict(json_schema_extra={"metadata": {
                "label": "Analyse_GitLab",
                "icon_url": "gitlab-icon.svg", # if exists
                "hidden": True,
                "sections": {
                    "auth": {
                        "required": True,
                        "subsections": [{"name": "Token", "fields": ["token"]}],
                    }
                },
            }})
        )

    @classmethod
    def get_toolkit(cls, client: "AlitaClient", selected_tools: list[str], **kwargs):
        bucket_path = kwargs.get("artifact_bucket_path") or "analyse-gitlab"
        artifact_wrapper = ArtifactWrapper(client=client, bucket=bucket_path)
        check_schema(artifact_wrapper)

        jira_project_keys = kwargs.get("jira_project_keys") or ""
        project_ids = kwargs.get("project_ids")  or ""
        url = kwargs.get("url")
        token = kwargs.get("token")

        if not url or not token:
            raise ValueError("GitLab URL and token are required.")

        gitlab_search = GitLabV4Search(
            url=url,
            default_branch_name=kwargs.get("default_branch_name", "master"),
            token=token,
        )

        gitlab_analyse_wrapper = GitLabAnalyseWrapper(
            artifacts_wrapper=artifact_wrapper,
            project_ids=project_ids,
            jira_project_keys=jira_project_keys,
            gitlab_search=gitlab_search,
        )

        selected_tools = selected_tools or []
        available_tools = gitlab_analyse_wrapper.get_available_tools()

        tools = []
        for tool in available_tools:
            if selected_tools:
                if tool["name"] not in selected_tools:
                    continue
            tools.append(
                BaseAction(
                    api_wrapper=gitlab_analyse_wrapper,
                    name=tool["name"],
                    description=tool["description"],
                    args_schema=tool["args_schema"],
                )
            )

        return cls(tools=tools)

    def get_tools(self):
        return self.tools
