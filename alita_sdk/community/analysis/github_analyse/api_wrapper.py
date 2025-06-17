import logging
from typing import Optional, Any
from langchain_core.callbacks import dispatch_custom_event
from pydantic import BaseModel, Field

from elitea_analyse.github.github_org import GitHubGetOrgLvl
from elitea_analyse.github.main_github import (
   extract_commits_from_multiple_repos,
   extract_pull_requests_from_multiple_repos,
   extract_repositories_list,
   extract_repositories_extended_data,
)

from alita_sdk.tools.elitea_base import BaseToolApiWrapper
from alita_sdk.runtime.utils.save_dataframe import save_dataframe_to_artifact
from alita_sdk.runtime.tools.artifact import ArtifactWrapper
from alita_sdk.runtime.utils.logging import with_streamlit_logs


logger = logging.getLogger(__name__)


class GetGithubCommitsFromReposArgs(BaseModel):
    since_after: str = Field( description="Date to filter commits from, in 'YYYY-MM-DD' format." )
    repos: Optional[str] = Field(
        description="Comma-separated list of repositories to extract commits from.",
        default="",
    )


class GetGithubRepositoriesListArgs(BaseModel):
    pushed_after: str = Field( description="Date to filter repositories by, in 'YYYY-MM-DD' format." )


class GitHubAnalyseWrapper(BaseToolApiWrapper):
    artifacts_wrapper: ArtifactWrapper
    repos: str  # Comma-separated list of GitHub repository names e.g. 'repo1,repo2'
    git: GitHubGetOrgLvl  # GitHub client

    class Config:
        arbitrary_types_allowed = True

    def get_commits_from_repos(self, since_after: str, repos: Optional[str] = None) -> str:
        """
        Extracts commit data from multiple GitHub repositories since the specified date. Saves the result to a CSV file.

        repos : str
            The string containing repositories names to extract data from, separated by commas.
        since_date : str
            The date to start extracting commits from, in 'YYYY-MM-DD' format.
        """
        repos = repos or self.repos
        df_commits = extract_commits_from_multiple_repos(repos, since_after, git=self.git)

        if df_commits is None or df_commits.empty:
            return f"No commits found for repositories: {repos} since {since_after}"

        output_filename = f"commits_{repos.replace(',', '_')}.csv"
        save_dataframe_to_artifact( self.artifacts_wrapper, df_commits, output_filename, {"index": False} )

        return f"GitHub commits data for {repos} saved to {output_filename}"

    def get_pull_requests_from_repos(self, since_after: str, repos: Optional[str] = None) -> str:
        """
        Extracts pull request data from multiple GitHub repositories since the specified date. 
        Saves the result to a CSV file.

        repos: str
            The string containing repositories names to extract data from, separated by commas.
        since_date: str
            The date to start extracting pull requests from, in 'YYYY-MM-DD' format.
        """
        repos = repos or self.repos
        df_pull_requests = extract_pull_requests_from_multiple_repos(repos, since_after, git=self.git)

        output_filename = f"pull_requests_details_{repos.replace(',', '_')}.csv"
        save_dataframe_to_artifact( self.artifacts_wrapper, df_pull_requests, output_filename, {"index": False} )

        return f"GitHub pull requests data saved to {output_filename}"

    def get_repositories_list(self, pushed_after: str) -> str:
        """
        Extracts a list of GitHub repositories that were pushed after the specified date. 
        Saves the result to a CSV file.

        pushed_after : str
            The date to filter repositories by, in 'YYYY-MM-DD' format.
        """
        df_repos = extract_repositories_list(pushed_after, git=self.git)

        output_filename = "github_repos_list.csv"
        save_dataframe_to_artifact( self.artifacts_wrapper, df_repos, output_filename, {"index": False} )
        dispatch_custom_event(
            "thinking_step",
            data={
                "message": f"Extracted {len(df_repos)} repositories pushed after {pushed_after}.",
                "tool_name": "github_repositories_list_extraction",
                "toolkit": "analyse_github",
            },
        )

        return f"GitHub repositories list saved to {output_filename}"

    @with_streamlit_logs(tool_name="get_github_repositories_extended_data")
    def get_repositories_extended_data(self, pushed_after: str) -> str:
        """
        Extracts extended information about GitHub repositories that were pushed after the specified date. 
        Saves the result to a CSV file.

        pushed_after : str
            The date to filter repositories by, in 'YYYY-MM-DD' format.
        """
        df_repos_extended = extract_repositories_extended_data(pushed_after, git=self.git)

        output_filename = "github_repos_extended_info.csv"
        save_dataframe_to_artifact( self.artifacts_wrapper, df_repos_extended, output_filename, {"index": False} )

        dispatch_custom_event(
            "thinking_step",
            data={
                "message": (
                    f"Extracted extended data for {len(df_repos_extended)} repositories "
                    f"pushed after {pushed_after}."
                ),
                "tool_name": "github_repositories_extended_data_extraction",
                "toolkit": "analyse_github",
            },
        )

        return f"Extended repository info that you have access saved to {output_filename}"

    def get_available_tools(self):
        """Get a list of available tools."""
        return [
            {
                "name": "get_commits_from_repos",
                "description": self.get_commits_from_repos.__doc__,
                "args_schema": GetGithubCommitsFromReposArgs,
                "ref": self.get_commits_from_repos,
            },
            {
                "name": "get_pull_requests_from_repos",
                "description": self.get_pull_requests_from_repos.__doc__,
                "args_schema": GetGithubCommitsFromReposArgs,
                "ref": self.get_pull_requests_from_repos,
            },
            {
                "name": "get_repositories_list",
                "description": self.get_repositories_list.__doc__,
                "args_schema": GetGithubRepositoriesListArgs,
                "ref": self.get_repositories_list,
            },
            {
                "name": "get_repositories_extended_data",
                "description": self.get_repositories_extended_data.__doc__,
                "args_schema": GetGithubRepositoriesListArgs,
                "ref": self.get_repositories_extended_data,
            },
        ]

    def run(self, mode: str, *args: Any, **kwargs: Any):
        for tool in self.get_available_tools():
            if tool["name"] == mode:
                return tool["ref"](*args, **kwargs)

        raise ValueError(f"Unknown mode: {mode}")
