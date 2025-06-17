import logging

from typing import Optional, Dict, Any
from langchain_core.callbacks import dispatch_custom_event
from pydantic import BaseModel, Field

from elitea_analyse.utils.constants import OUTPUT_WORK_ITEMS_FILE
from elitea_analyse.ado.azure_search import AzureSearch
from elitea_analyse.ado.main import (
    OUTPUT_WORK_ITEMS,
    get_work_items_several_projects,
    get_commits_several_projects,
    get_merge_requests_several_projects,
    get_pipelines_runs_several_projects,
)


from alita_sdk.tools.elitea_base import BaseToolApiWrapper

from alita_sdk.runtime.utils.save_dataframe import save_dataframe_to_artifact
from alita_sdk.runtime.tools.artifact import ArtifactWrapper
from alita_sdk.runtime.utils.logging import with_streamlit_logs


logger = logging.getLogger(__name__)

class NoInputArgs(BaseModel):
    pass

class GetAdoWorkItemsArgs(BaseModel):
    resolved_after: str = Field(description="Resolveed after date (i.e. 2023-01-01)")
    updated_after: str = Field(description="Updated after date (i.e. 2023-01-01)")
    created_after: str = Field(description="Created after date (i.e. 2023-01-01)")
    area: Optional[str] = Field(description="Area path filter.", default="")
    project_keys: Optional[str] = Field(
        description="One or more projects keys separated with comma.", default=""
    )


class AdoCommitsArgs(BaseModel):
    project_keys: Optional[str] = Field(
        description="One or more projects keys separated with comma.", default=""
    )
    since_date: str = Field(description="Get commits after this date 'YYYY-MM-DD'")


class AdoPipelinesArgs(BaseModel):
    project_keys: Optional[str] = Field(
        description="One or more projects keys separated with comma.", default=""
    )


class AdoAnalyseWrapper(BaseToolApiWrapper):
    artifacts_wrapper: ArtifactWrapper
    project_keys: str  # Comma-separated list of Azure DevOps project names
    default_branch_name: str = "main"
    area: str = ""
    ado_search: AzureSearch  # Azure DevOps search client

    class Config:
        arbitrary_types_allowed = True

    def get_projects_list(self):
        """
        Get all projects in the organization that the authenticated user has access to.
        Details on a page: https://docs.microsoft.com/en-us/rest/api/azure/devops/core/projects/list
        """
        result = self.ado_search.get_projects_list()

        save_dataframe_to_artifact(
            self.artifacts_wrapper,
            result,
            "projects_info.csv",
            csv_options={"index": False},
        )

        return (
            f"You have access to {len(result)} project. "
            f"Data has been downloaded to the bucket as 'projects_info.csv'."
        )

    @with_streamlit_logs(tool_name="get_work_items")
    def get_work_items(
        self,
        resolved_after: str,
        updated_after: str,
        created_after: str,
        area: str = "",
        project_keys: Optional[str] = None,
    ) -> str:
        """
        Get work items from multiple Azure DevOps projects.

            project_keys: str
                Comma-separated project names.
            resolved_after: str
                Date filter for resolved items 'YYYY-MM-DD'.
            updated_after: str
                Date filter for updated items 'YYYY-MM-DD'.
            created_after: str
                Date filter for created items 'YYYY-MM-DD'.
            area: str
                Area path filter (optional).
        """
        project_keys = project_keys or self.project_keys
        area = area or self.area

        df_work_items = get_work_items_several_projects(
            project_keys,
            resolved_after,
            updated_after,
            created_after,
            area=area,
            ado_search=self.ado_search,
        )

        save_dataframe_to_artifact(
            self.artifacts_wrapper,
            df_work_items,
            f"{OUTPUT_WORK_ITEMS_FILE}{project_keys}.csv",
            csv_options={"index_label": "id"},
        )

        return (
            f"Work items for {project_keys} have been successfully retrieved "
            f"and saved to the bucket as '{OUTPUT_WORK_ITEMS}{project_keys}.csv'."
        )

    async def get_commits(
        self,
        since_date: str,
        project_keys: Optional[str] = None,
        new_version: bool = True,
        with_commit_size: bool = True,
    ) -> str:
        """
        Get commits from multiple Azure DevOps projects.

        since_date: str
            Get commits after this date 'YYYY-MM-DD'.
        project_keys: str
            Comma-separated project names.
        new_version: bool
            Use new API version.
        with_commit_size: bool
            Include commit size info.
        """
        project_keys = project_keys or self.project_keys

        # Await the coroutine to get commits
        df_commits = await get_commits_several_projects(
            project_keys,
            since_date,
            new_version=new_version,
            with_commit_size=with_commit_size,
            ado_search=self.ado_search,
        )

        save_dataframe_to_artifact(
            self.artifacts_wrapper,
            df_commits,
            f"commits_details_{project_keys}.csv",
            csv_options={"index_label": "id"},
        )

        return (
            f"Commits for {project_keys} have been successfully retrieved "
            f"and saved to the bucket as 'commits_details_{project_keys}.csv'."
        )

    def get_merge_requests(
        self, since_date: str, project_keys: Optional[str] = None
    ) -> str:
        """
        Get pull requests from multiple Azure DevOps projects.

        project_keys: str
            Comma-separated project names.
        since_date: str
            Get PRs after this date 'YYYY-MM-DD'.
        """
        project_keys = project_keys or self.project_keys

        df_prs = get_merge_requests_several_projects(
            project_keys, since_date, ado_search=self.ado_search
        )

        save_dataframe_to_artifact(
            self.artifacts_wrapper,
            df_prs,
            f"merge_requests_details_{project_keys}.csv",
            csv_options={"index": False},
        )

        return (
            f"Pull requests for {project_keys} have been successfully retrieved "
            f"and saved to the bucket as 'merge_requests_details_{project_keys}.csv'."
        )

    def get_pipelines_runs(
        self,
        project_keys: Optional[str] = None,
    ) -> str:
        """
        Get pipeline runs from multiple Azure DevOps projects.

        project_keys: str
            Comma-separated project names.
        """
        project_keys = project_keys or self.project_keys
        pipelines_df = get_pipelines_runs_several_projects(project_keys, ado_search=self.ado_search)

        save_dataframe_to_artifact(
            self.artifacts_wrapper, pipelines_df, f"pipelines_runs_{project_keys}.csv", csv_options={"index": False}
         )

        return (
            f"Pipeline runs for {project_keys} have been successfully retrieved "
            f"and saved to the bucket as 'pipelines_runs_{project_keys}.csv'."
        )

    def get_available_tools(self) -> list[Dict[str, Any]]:
        """Get a list of available tools."""
        return [
            {
                "name": "get_projects_list",
                "description": self.get_projects_list.__doc__,
                "ref": self.get_projects_list,
                "args_schema": NoInputArgs,
            },
            {
                "name": "get_work_items",
                "description": self.get_work_items.__doc__,
                "ref": self.get_work_items,
                "args_schema": GetAdoWorkItemsArgs,
            },
            {
                "name": "get_commits",
                "description": self.get_commits.__doc__,
                "ref": self.get_commits,
                "args_schema": AdoCommitsArgs,
            },
            {
                "name": "get_merge_requests",
                "description": self.get_merge_requests.__doc__,
                "ref": self.get_merge_requests,
                "args_schema": AdoCommitsArgs,
            },
            {
                "name": "get_pipelines_runs",
                "description": self.get_pipelines_runs.__doc__,
                "ref": self.get_pipelines_runs,
                "args_schema": AdoPipelinesArgs,
            },
        ]

    def run(self, mode: str, *args: Any, **kwargs: Any):
        for tool in self.get_available_tools():
            if tool["name"] == mode:
                return tool["ref"](*args, **kwargs)
        raise ValueError(f"Unknown mode: {mode}")
