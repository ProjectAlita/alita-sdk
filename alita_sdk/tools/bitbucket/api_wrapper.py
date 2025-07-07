"""Util that calls Bitbucket."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from langchain_core.tools import ToolException
from pydantic import BaseModel, model_validator, SecretStr
from .bitbucket_constants import create_pr_data
from .cloud_api_wrapper import BitbucketCloudApi, BitbucketServerApi
from pydantic.fields import PrivateAttr

from ..elitea_base import BaseCodeToolApiWrapper

logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    pass


class BitbucketAPIWrapper(BaseCodeToolApiWrapper):
    """Wrapper for Bitbucket API."""

    _bitbucket: Any = PrivateAttr()
    _active_branch: Any = PrivateAttr() 
    url: str = ''
    project: str = ''
    """The key of the project this repo belongs to"""
    repository: str = ''
    """The name of the Bitbucket repository"""
    username: str = None
    """Username required for authentication."""
    password: SecretStr = None
    # """User's password or OAuth token required for authentication."""
    branch: Optional[str] = 'main'
    """The specific branch in the Bitbucket repository where the bot will make 
        its commits. Defaults to 'main'.
    """
    cloud: Optional[bool] = False
    """Bitbucket installation type: true for cloud, false for server.
    """

    @model_validator(mode='before')
    @classmethod
    def validate_env(cls, values: Dict) -> Dict:
        """Validate authentication and python package existence in environment."""
        try:
            import atlassian

        except ImportError:
            raise ImportError(
                "atlassian-python-api is not installed. "
                "Please install it with `pip install atlassian-python-api`"
            )
        cls._bitbucket = BitbucketCloudApi(
            url=values['url'],
            username=values['username'],
            password=values['password'],
            workspace=values['project'],
            repository=values['repository']
        ) if values['cloud'] else BitbucketServerApi(
            url=values['url'],
            username=values['username'],
            password=values['password'],
            project=values['project'],
            repository=values['repository']
        )
        cls._active_branch = values.get('branch')
        return values

    def set_active_branch(self, branch: str) -> None:
        """Set the active branch for the bot."""
        self._active_branch = branch
        return f"Active branch set to `{branch}`"

    def list_branches_in_repo(self) -> List[str]:
        """List all branches in the repository."""
        return self._bitbucket.list_branches()

    def create_branch(self, branch_name: str) -> None:
        """Create a new branch in the repository."""
        try:
            self._bitbucket.create_branch(branch_name, self._active_branch)
        except Exception as e:
            if "not permitted to access this resource" in str(e):
                return f"Please, verify you token/password: {str}"
            if "already exists" in str(e):
                self._active_branch = branch_name
                return f"Branch {branch_name} already exists. set it as active"
            return f"Unable to create branch due to error:\n{e}"
        self._active_branch = branch_name
        return f"Branch {branch_name} created successfully and set as active"

    def create_pull_request(self, pr_json_data: str) -> str:
        """
        Makes a pull request from the bot's branch to the base branch
        Parameters:
            pr_json_data(str): a JSON string which contains information on how pull request should be done
        Returns:
            str: A success or failure message
        """
        try:
            pr = self._bitbucket.create_pull_request(pr_json_data)
            return f"Successfully created PR\n{str(pr)}"
        except Exception as e:
            if "Bad request" in str(e):
                logger.info(f"Make sure your pr_json matches to {create_pr_data}")
                raise ToolException(f"Make sure your pr_json matches to data json format {create_pr_data}.\nOrigin exception: {e}")
            raise ToolException(e)

    def create_file(self, file_path: str, file_contents: str, branch: str) -> str:
        """
        Creates a new file on the bitbucket repo
        Parameters:
            file_path(str): a string which contains the file path (example: "hello_world.md").
            file_contents(str): a string which the file contents (example: "# Hello World!").
            branch(str): branch name (by default: active_branch)
        Returns:
            str: A success or failure message
        """
        try:
            self._bitbucket.create_file(file_path=file_path, file_contents=file_contents, branch=branch)
            return f"File has been created: {file_path}."
        except Exception as e:
            return ToolException(f"File was not created due to error: {str(e)}")

    def update_file(self, file_path: str, update_query: str, branch: str) -> ToolException | str:
        """
        Updates file on the bitbucket repo
        Parameters:
            file_path(str): a string which contains the file path (example: "hello_world.md").
            update_query(str): Contains the file contents requried to be updated.
                The old file contents is wrapped in OLD <<<< and >>>> OLD
                The new file contents is wrapped in NEW <<<< and >>>> NEW
                For example:
                OLD <<<<
                Hello Earth!
                >>>> OLD
                NEW <<<<
                Hello Mars!
                >>>> NEW
            branch(str): branch name (by default: active_branch)
        Returns:
            str: A success or failure message
        """
        try:
            result = self._bitbucket.update_file(file_path=file_path, update_query=update_query, branch=branch)
            return result if isinstance(result, ToolException) else f"File has been updated: {file_path}."
        except Exception as e:
            return ToolException(f"File was not updated due to error: {str(e)}")
    
    def get_pull_requests_commits(self, pr_id: str) -> List[Dict[str, Any]]:
        """
        Get commits from a pull request
        Parameters:
            pr_id(str): the pull request ID
        Returns:
            List[Dict[str, Any]]: List of commits in the pull request
        """
        try:
            result = self._bitbucket.get_pull_request_commits(pr_id=pr_id)
            return result
        except Exception as e:
            return ToolException(f"Can't get commits from pull request `{pr_id}` due to error:\n{str(e)}")
        
    def get_pull_requests(self) -> List[Dict[str, Any]]:
        """
        Get pull requests from the repository
        Returns:
            List[Dict[str, Any]]: List of pull requests in the repository
        """
        return self._bitbucket.get_pull_requests()
    
    def get_pull_request(self, pr_id: str) -> Any:
        """
        Get details of a pull request
        Parameters:
            pr_id(str): the pull request ID
        Returns:
            Any: Details of the pull request
        """
        try:
            return self._bitbucket.get_pull_request(pr_id=pr_id)
        except Exception as e:
            return ToolException(f"Can't get pull request `{pr_id}` due to error:\n{str(e)}")
        
    def get_pull_requests_changes(self, pr_id: str) -> Any:
        """
        Get changes of a pull request
        Parameters:
            pr_id(str): the pull request ID
        Returns:
            Any: Changes of the pull request
        """
        try:
            return self._bitbucket.get_pull_requests_changes(pr_id=pr_id)
        except Exception as e:
            return ToolException(f"Can't get changes from pull request `{pr_id}` due to error:\n{str(e)}")
        
    def add_pull_request_comment(self, pr_id: str, content, inline=None) -> str:
        """
        Add a comment to a pull request. Supports multiple content types and inline comments.
        Parameters:
            pr_id (str): the pull request ID
            content (str or dict): The comment content. Can be a string (raw text) or a dict with keys 'raw', 'markup', 'html'.
            inline (dict, optional): Inline comment details. Example: {"from": 57, "to": 122, "path": "<string>"}
        Returns:
            str: A success or failure message
        """
        try:
            return self._bitbucket.add_pull_request_comment(pr_id=pr_id, content=content, inline=inline)
        except Exception as e:
            return ToolException(f"Can't add comment to pull request `{pr_id}` due to error:\n{str(e)}")

    def _get_files(self, file_path: str, branch: str) -> str:
        """
        Get files from the bitbucket repo
        Parameters:
            file_path(str): the file path
            branch(str): branch name (by default: active_branch)
        Returns:
            str: List of the files
        """
        return str(self._bitbucket.get_files_list(file_path=file_path if file_path else '', branch=branch if branch else self._active_branch))

    def _read_file(self, file_path: str, branch: str) -> str:
        """
        Reads a file from the gitlab repo
        Parameters:
            file_path(str): the file path
            branch(str): branch name (by default: active_branch)
        Returns:
            str: The file decoded as a string
        """
        try:
            return self._bitbucket.get_file(file_path=file_path, branch=branch)
        except Exception as e:
            raise ToolException(f"Can't extract file content (`{file_path}`) due to error:\n{str(e)}")
