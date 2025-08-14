from typing import Any, Dict, List, Optional, Union, Tuple
import logging
import traceback
import json
import re
from pydantic import BaseModel, model_validator, Field, SecretStr

from .github_client import GitHubClient
from .graphql_client_wrapper import GraphQLClientWrapper
from .schemas import (
    GitHubAuthConfig,
    GitHubRepoConfig
)

from ..elitea_base import BaseCodeToolApiWrapper

from langchain_core.callbacks import dispatch_custom_event

logger = logging.getLogger(__name__)

# Import prompts for tools
from .tool_prompts import (
    UPDATE_FILE_PROMPT,
    CREATE_ISSUE_PROMPT,
    UPDATE_ISSUE_PROMPT,
    CREATE_ISSUE_ON_PROJECT_PROMPT,
    UPDATE_ISSUE_ON_PROJECT_PROMPT
)

# Create schema models for the new indexing functionality
from pydantic import create_model
from typing import Literal


class AlitaGitHubAPIWrapper(BaseCodeToolApiWrapper):
    """
    Wrapper for GitHub API that integrates both REST and GraphQL functionality.
    """
    # Authentication config
    github_access_token: Optional[SecretStr] = None
    github_username: Optional[SecretStr] = None
    github_password: Optional[SecretStr] = None
    github_app_id: Optional[str] = None
    github_app_private_key: Optional[str] = None
    github_base_url: Optional[str] = None

    # Repository config
    github_repository: Optional[str] = None
    active_branch: Optional[str] = None
    github_base_branch: Optional[str] = None

    # Alita instance
    alita: Optional[Any] = None
    
    # Client instances - renamed without leading underscores and marked as exclude=True
    github_client_instance: Optional[GitHubClient] = Field(default=None, exclude=True)
    graphql_client_instance: Optional[GraphQLClientWrapper] = Field(default=None, exclude=True)

    class Config:
        arbitrary_types_allowed = True

    @model_validator(mode='before')
    @classmethod
    def validate_environment(cls, values: Dict) -> Dict:
        """
        Initialize GitHub clients based on the provided values.

        Args:
            values (Dict): Configuration values for GitHub API wrapper

        Returns:
            Dict: Updated values dictionary
        """
        from langchain.utils import get_from_dict_or_env

        # Get all authentication values
        github_access_token = get_from_dict_or_env(values, ["access_token", "github_access_token"], "GITHUB_ACCESS_TOKEN", default='')
        github_username = get_from_dict_or_env(values, ["username", "github_username"], "GITHUB_USERNAME", default='')
        github_password = get_from_dict_or_env(values, ["password", "github_password"], "GITHUB_PASSWORD", default='')
        github_app_id = get_from_dict_or_env(values, ["app_id", "github_app_id"], "GITHUB_APP_ID", default='')
        github_app_private_key = get_from_dict_or_env(values, ["app_private_key", "github_app_private_key"], "GITHUB_APP_PRIVATE_KEY", default='')
        github_base_url = get_from_dict_or_env(values, ["base_url", "github_base_url"], "GITHUB_BASE_URL", default='https://api.github.com')

        auth_config = GitHubAuthConfig(
            github_access_token=github_access_token,
            github_username=github_username,
            github_password=github_password,
            github_app_id=github_app_id,  # This will be None if not provided - GitHubAuthConfig should allow this
            github_app_private_key=github_app_private_key,
            github_base_url=github_base_url
        )

        # Rest of initialization code remains the same
        github_repository = get_from_dict_or_env(values, "github_repository", "GITHUB_REPOSITORY")
        github_repository = GitHubClient.clean_repository_name(github_repository)

        repo_config = GitHubRepoConfig(
            github_repository=github_repository,
            active_branch=get_from_dict_or_env(values, "active_branch", "ACTIVE_BRANCH", default='main'),  # Change from 'ai' to 'main'
            github_base_branch=get_from_dict_or_env(values, "github_base_branch", "GITHUB_BASE_BRANCH", default="main")
        )

        # Initialize GitHub client with keyword arguments
        github_client = GitHubClient(auth_config=auth_config, repo_config=repo_config, alita=values.get("alita"))
        # Initialize GraphQL client with keyword argument
        graphql_client = GraphQLClientWrapper(github_graphql_instance=github_client.github_api._Github__requester)
        # Set client attributes on the class (renamed from _github_client to github_client_instance)
        values["github_client_instance"] = github_client
        values["graphql_client_instance"] = graphql_client

        # Update values
        values["github_repository"] = github_repository
        values["active_branch"] = repo_config.active_branch
        values["github_base_branch"] = repo_config.github_base_branch

        # Ensure LLM is available in values if needed
        if "llm" not in values:
            values["llm"] = None

        return values

    # Expose GitHub REST client methods directly via property
    @property
    def github_client(self) -> GitHubClient:
        """Access to GitHub REST client methods"""
        return self.github_client_instance

    # Expose GraphQL client methods directly via property
    @property
    def graphql_client(self) -> GraphQLClientWrapper:
        """Access to GitHub GraphQL client methods"""
        return self.graphql_client_instance


    def get_available_tools(self):
        # this is horrible, I need to think on something better
        if not self.github_client_instance:
            github_tools = GitHubClient.model_construct().get_available_tools()
        else:
            github_tools = self.github_client_instance.get_available_tools()
        if not self.graphql_client_instance:
            graphql_tools = GraphQLClientWrapper.model_construct().get_available_tools()
        else:
            graphql_tools = self.graphql_client_instance.get_available_tools()
            
        # Add vector search tools from base class (includes index_data + search tools)
        vector_search_tools = self._get_vector_search_tools()
        
        tools = github_tools + graphql_tools + vector_search_tools
        return tools

    def _get_files(self, path: str = "", branch: str = None):
        """Get list of files from GitHub repository."""
        if not self.github_client_instance:
            raise ValueError("GitHub client not initialized")
        
        # Use the GitHub client's method to get files
        return self.github_client_instance._get_files(path, branch or self.active_branch)

    def _file_commit_hash(self, file_path: str, branch: str):
        """Get the commit hash of a file in the GitHub repository."""
        if not self.github_client_instance:
            raise ValueError("GitHub client not initialized")

        # Use the GitHub client's method to get commit hash
        return self.github_client_instance._file_commit_hash(file_path, branch or self.active_branch)

    def _read_file(self, file_path: str, branch: str):
        """Read file content from GitHub repository."""
        if not self.github_client_instance:
            raise ValueError("GitHub client not initialized")
        
        # Use the GitHub client's method to read file
        return self.github_client_instance._read_file(file_path, branch)

    def run(self, name: str, *args: Any, **kwargs: Any):
        for tool in self.get_available_tools():
            if tool["name"] == name:
                # Handle potential dictionary input for args when only one dict is passed
                if len(args) == 1 and isinstance(args[0], dict) and not kwargs:
                     kwargs = args[0]
                     args = () # Clear args
                try:
                    return tool["ref"](*args, **kwargs)
                except TypeError as e:
                     # Attempt to call with kwargs only if args fail and kwargs exist
                     if kwargs and not args:
                         try:
                             return tool["ref"](**kwargs)
                         except TypeError:
                             raise ValueError(f"Argument mismatch for tool '{name}'. Error: {e}") from e
                     else:
                         raise ValueError(f"Argument mismatch for tool '{name}'. Error: {e}") from e
        else:
            raise ValueError(f"Unknown tool name: {name}")
