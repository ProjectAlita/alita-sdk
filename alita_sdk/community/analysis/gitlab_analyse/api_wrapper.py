import logging
from typing import Any
from pydantic import BaseModel, Field
from typing import Optional

from elitea_analyse.git.main import (
    get_git_projects_list,
    get_git_projects_that_in_jira,
    get_git_commits,
    get_git_merge_requests,
)
from elitea_analyse.git.git_search import GitLabV4Search


from alita_sdk.tools.elitea_base import BaseToolApiWrapper
from alita_sdk.runtime.utils.save_dataframe import save_dataframe_to_artifact
from alita_sdk.runtime.tools.artifact import ArtifactWrapper


logger = logging.getLogger(__name__)


class GitLabProjectsListArgs(BaseModel):
    date: str = Field(
        description="Filter projects by last activity date in 'YYYY-MM-DD' format."
    )

class GitLabProjectsListInJiraArgs(BaseModel):
    jira_project_keys: Optional[str] = Field(description="Comma-separated Jira project keys.", default=None)

class GitLabCommitsArgs(BaseModel):
    project_ids: Optional[str] = Field(description="GitLab project ID.", default=None)
    since_date:str = Field(description="Date filter in 'YYYY-MM-DD' format.")


class GitLabAnalyseWrapper(BaseToolApiWrapper):
    artifacts_wrapper: ArtifactWrapper
    project_ids: str  # Comma-separated list of GitLab project IDs
    jira_project_keys: str  # Comma-separated list of Jira projects' keys
    gitlab_search: GitLabV4Search  # GitLab search client

    class Config:
        arbitrary_types_allowed = True

    def get_gitlab_projects_list(self, date: str) -> str:
        """
        Get projects list that user has access to in GitLab.

        date: str
            Filter projects by last activity date.
            Date in 'YYYY-MM-DD' format.
        """

        df_project_list = get_git_projects_list(date, git=self.gitlab_search)

        save_dataframe_to_artifact(
            self.artifacts_wrapper, df_project_list, "gitlab_projects_info.csv", csv_options={"index": False}
        )

        return (
            f"You have access to {len(df_project_list)}. "
            f"Data has been downloaded to the bucket as 'gitlab_projects_info.csv'"
        )

    def get_gitlab_projects_that_in_jira(self, jira_project_keys: Optional[str] = None) -> str:
        """
        Find GitLab projects that correspond to Jira projects by matching names.

        jira_project_keys: str
            Comma-separated Jira project keys.
        """
        jira_project_keys = jira_project_keys or self.jira_project_keys
        df_projects = get_git_projects_that_in_jira(
            jira_project_keys, git=self.gitlab_search)

        if df_projects is None or df_projects.empty:
            return "No GitLab projects found that match the provided Jira project keys."

        save_dataframe_to_artifact(
            self.artifacts_wrapper, df_projects, "gitlab_projects_that_in_Jira.csv", csv_options={"index": False},
        )

        return (
            f"Found {len(df_projects)} GitLab projects that match Jira project names. "
            f"Data has been downloaded to the bucket as 'gitlab_projects_that_in_Jira.csv'."
        )

    def get_gitlab_commits(self, since_date: str, project_ids: Optional[str] = None) -> str:
        """
        Get commit data for specified GitLab project.

        project_id: str
            GitLab project ID.
        since_date: str
            Date filter in 'YYYY-MM-DD' format.
        """
        project_ids = project_ids or self.project_ids
        df_commits = get_git_commits(
            project_ids, since_date, git_search=self.gitlab_search
        )

        if df_commits is None or df_commits.empty:
            return f'There are no commits in the project {project_ids} created after {since_date}'

        save_dataframe_to_artifact(
            self.artifacts_wrapper, df_commits, f"commits_details_{project_ids}.csv", csv_options={"index": False},
        )

        return (
            f"Commits data for project {project_ids} has been saved. "
            f"Data has been downloaded to the bucket as 'commits_details_{project_ids}.csv'."
        )

    def get_gitlab_merge_requests(self, since_date: str, project_ids: Optional[str] = None) -> str:
        """
        Get merge requests for specified GitLab project.

        project_ids: str
            GitLab project ID.
        since_date: str
            Date filter in 'YYYY-MM-DD' format.
        """
        project_ids = project_ids or self.project_ids
        df_mrs = get_git_merge_requests(
            project_ids, since_date, git_search=self.gitlab_search)

        if df_mrs is None or df_mrs.empty:
            return f'There are no merge requests in the project {project_ids} created after {since_date}'

        save_dataframe_to_artifact(
            self.artifacts_wrapper, df_mrs, f"merge_requests_details_{project_ids}.csv", csv_options={"index": False},
        )

        return (
            f"Merge requests data for project {project_ids} has been saved. "
            f"Data has been downloaded to the bucket as 'merge_requests_details_{project_ids}.csv'."
        )


    def get_available_tools(self):
        return [
            {
                "name": "get_gitlab_projects_list",
                "description": self.get_gitlab_projects_list.__doc__,
                "args_schema": GitLabProjectsListArgs ,
                "ref": self.get_gitlab_projects_list
            },
            {
                "name": "get_gitlab_projects_that_in_jira",
                "description": self.get_gitlab_projects_that_in_jira.__doc__,
                "args_schema": GitLabProjectsListInJiraArgs,
                "ref": self.get_gitlab_projects_that_in_jira
            },
            {
                "name": "get_gitlab_commits",
                "description": self.get_gitlab_commits.__doc__,
                "args_schema": GitLabCommitsArgs,
                "ref": self.get_gitlab_commits
            },
            {
                "name": "get_gitlab_merge_requests",
                "description": self.get_gitlab_merge_requests.__doc__,
                "args_schema": GitLabCommitsArgs,
                "ref": self.get_gitlab_merge_requests
            }
        ]

    def run(self, mode: str, *args: Any, **kwargs: Any):
        for tool in self.get_available_tools():
            if tool["name"] == mode:
                return tool["ref"](*args, **kwargs)
        raise ValueError(f"Unknown mode: {mode}")
