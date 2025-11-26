"""Util that calls Bitbucket."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
import fnmatch

from langchain_core.tools import ToolException
from pydantic import model_validator, SecretStr, create_model, Field
from .bitbucket_constants import create_pr_data
from .cloud_api_wrapper import BitbucketCloudApi, BitbucketServerApi
from pydantic.fields import PrivateAttr

from ..code_indexer_toolkit import CodeIndexerToolkit
from ..utils.available_tools_decorator import extend_with_parent_available_tools

logger = logging.getLogger(__name__)

# Pydantic model definitions for tool arguments
CreateBranchModel = create_model(
    "CreateBranchModel",
    branch_name=(str, Field(description="The name of the branch, e.g. `my_branch`.")),
)

CreatePullRequestModel = create_model(
    "CreatePullRequestModel",
    pr_json_data=(str, Field(description=create_pr_data)),
)

CreateFileModel = create_model(
    "CreateFileModel",
    file_path=(str, Field(description="The path of the file")),
    file_contents=(str, Field(description="The contents of the file")),
    branch=(str, Field(description="The branch to create the file in")),
)

UpdateFileModel = create_model(
    "UpdateFileModel",
    file_path=(str, Field(description="The path of the file")),
    update_query=(str, Field(description="Contains the file contents required to be updated. "
                                       "The old file contents is wrapped in OLD <<<< and >>>> OLD. "
                                       "The new file contents is wrapped in NEW <<<< and >>>> NEW")),
    branch=(str, Field(description="The branch to update the file in")),
)

ReadFileModel = create_model(
    "ReadFileModel",
    file_path=(str, Field(description="The path of the file")),
    branch=(str, Field(description="The branch to read the file from")),
)

SetActiveBranchModel = create_model(
    "SetActiveBranchModel",
    branch_name=(str, Field(description="The name of the branch, e.g. `my_branch`.")),
)

ListBranchesInRepoModel = create_model(
    "ListBranchesInRepoModel",
    limit=(Optional[int], Field(default=20, description="Maximum number of branches to return. If not provided, all branches will be returned.")),
    branch_wildcard=(Optional[str], Field(default=None, description="Wildcard pattern to filter branches by name. If not provided, all branches will be returned."))
)

ListFilesModel = create_model(
    "ListFilesModel",
    path=(Optional[str], Field(description="The path to list files from", default=None)),
    recursive=(bool, Field(description="Whether to list files recursively", default=True)),
    branch=(Optional[str], Field(description="The branch to list files from")),
)

GetPullRequestsCommitsModel = create_model(
    "GetPullRequestsCommitsModel",
    pr_id=(str, Field(description="The ID of the pull request to get commits from")),
)

GetPullRequestModel = create_model(
    "GetPullRequestModel",
    pr_id=(str, Field(description="The ID of the pull request to get details from")),
)

GetPullRequestsChangesModel = create_model(
    "GetPullRequestsChangesModel",
    pr_id=(str, Field(description="The ID of the pull request to get changes from")),
)

AddPullRequestCommentModel = create_model(
    "AddPullRequestCommentModel",
    pr_id=(str, Field(description="The ID of the pull request to add a comment to")),
    content=(str, Field(description="The comment content")),
    inline=(Optional[dict], Field(default=None, description="Inline comment details. Example: {'from': 57, 'to': 122, 'path': '<string>'}"))
)

DeleteFileModel = create_model(
    "DeleteFileModel",
    file_path=(str, Field(description="The path of the file")),
    branch=(str, Field(description="The branch to delete the file from")),
    commit_message=(str, Field(default=None, description="Commit message for deleting the file. Optional.")),
)

AppendFileModel = create_model(
    "AppendFileModel",
    file_path=(str, Field(description="The path of the file")),
    content=(str, Field(description="The content to append to the file")),
    branch=(str, Field(description="The branch to append the file in")),
)

GetIssuesModel = create_model(
    "GetIssuesModel",
)

GetIssueModel = create_model(
    "GetIssueModel",
    issue_number=(int, Field(description="The number of the issue")),
)

CommentOnIssueModel = create_model(
    "CommentOnIssueModel",
    comment_query=(str, Field(description="The comment query string")),
)


class BitbucketAPIWrapper(CodeIndexerToolkit):
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
        from langchain_core.utils import get_from_dict_or_env
        url_value = get_from_dict_or_env(values, ["url"], "BITBUCKET_BASE_URL", default='https://api.bitbucket.org/')
        cls._bitbucket = BitbucketCloudApi(
            url=url_value,
            username=values['username'],
            password=values['password'],
            workspace=values['project'],
            repository=values['repository']
        ) if values.get('cloud') else BitbucketServerApi(
            url=values['url'],
            username=values['username'],
            password=values['password'],
            project=values['project'],
            repository=values['repository']
        )
        cls._active_branch = values.get('branch')
        return super().validate_toolkit(values)

    def set_active_branch(self, branch_name: str) -> str:
        """Set the active branch for the bot."""
        self._active_branch = branch_name
        return f"Active branch set to `{branch_name}`"

    def list_branches_in_repo(self, limit: Optional[int] = 20, branch_wildcard: Optional[str] = None) -> List[str]:
        """
        Lists branches in the repository with optional limit and wildcard filtering.

        Parameters:
            limit (Optional[int]): Maximum number of branches to return
            branch_wildcard (Optional[str]): Wildcard pattern to filter branches (e.g., '*dev')

        Returns:
            List[str]: List containing names of branches
        """
        try:
            branches = self._bitbucket.list_branches()

            if branch_wildcard:
                branches = [branch for branch in branches if fnmatch.fnmatch(branch, branch_wildcard)]

            if limit is not None:
                branches = branches[:limit]

            return "Found branches: " + ", ".join(branches)
        except Exception as e:
            return f"Failed to list branches: {str(e)}"

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

    def get_pull_request(self, pr_id: str) -> Dict[str, Any]:
        """
        Get details of a pull request
        Parameters:
            pr_id(str): the pull request ID
        Returns:
            dict: Details of the pull request as a dictionary
        """
        try:
            return self._bitbucket.get_pull_request(pr_id=pr_id)
        except Exception as e:
            return ToolException(f"Can't get pull request `{pr_id}` due to error:\n{str(e)}")

    def get_pull_requests_changes(self, pr_id: str) -> Dict[str, Any]:
        """
        Get changes of a pull request
        Parameters:
            pr_id(str): the pull request ID
        Returns:
            dict: Changes of the pull request as a dictionary
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

    def _get_files(self, path: str, branch: str) -> str:
        """
        Get files from the bitbucket repo
        Parameters:
            path(str): the file path
            branch(str): branch name (by default: active_branch)
        Returns:
            str: List of the files
        """
        return str(self._bitbucket.get_files_list(file_path=path if path else '', branch=branch if branch else self._active_branch))

    # TODO: review this method, it may not work as expected
    # def _file_commit_hash(self, file_path: str, branch: str):
    #     """
    #     Get the commit hash of a file in the gitlab repo
    #     Parameters:
    #         file_path(str): the file path
    #         branch(str): branch name (by default: active_branch)
    #     Returns:
    #         str: The commit hash of the file
    #     """
    #     try:
    #         return self._bitbucket.get_file_commit_hash(file_path=file_path, branch=branch)
    #     except Exception as e:
    #         raise ToolException(f"Can't extract file commit hash (`{file_path}`) due to error:\n{str(e)}")

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

    def list_files(self, path: str = None, recursive: bool = True, branch: str = None) -> List[str]:
        """List files in the repository with optional path, recursive search, and branch."""
        branch = branch if branch else self._active_branch
        try:
            files_str = self._get_files(path, branch)
            # Parse the string response to extract file paths
            # This is a simplified implementation - might need adjustment based on actual response format
            import ast
            try:
                files_list = ast.literal_eval(files_str)
                if isinstance(files_list, list):
                    return files_list
                else:
                    return [str(files_list)]
            except:
                return [files_str] if files_str else []
        except Exception as e:
            return f"Failed to list files: {str(e)}"

    def read_file(self, file_path: str, branch: str) -> str:
        """Read the contents of a file in the repository."""
        try:
            return self._read_file(file_path, branch)
        except Exception as e:
            return f"Failed to read file {file_path}: {str(e)}"

    @extend_with_parent_available_tools
    def get_available_tools(self):
        return [
            {
                "name": "create_branch",
                "ref": self.create_branch,
                "description": self.create_branch.__doc__ or "Create a new branch in the repository.",
                "args_schema": CreateBranchModel,
            },
            {
                "name": "list_branches_in_repo",
                "ref": self.list_branches_in_repo,
                "description": self.list_branches_in_repo.__doc__ or "List branches in the repository with optional limit and wildcard filtering.",
                "args_schema": ListBranchesInRepoModel,
            },
            {
                "name": "list_files",
                "ref": self.list_files,
                "description": self.list_files.__doc__ or "List files in the repository with optional path, recursive search, and branch.",
                "args_schema": ListFilesModel,
            },
            {
                "name": "create_pull_request",
                "ref": self.create_pull_request,
                "description": self.create_pull_request.__doc__ or "Create a pull request in the repository.",
                "args_schema": CreatePullRequestModel,
            },
            {
                "name": "create_file",
                "ref": self.create_file,
                "description": self.create_file.__doc__ or "Create a new file in the repository.",
                "args_schema": CreateFileModel,
            },
            {
                "name": "read_file",
                "ref": self.read_file,
                "description": self.read_file.__doc__ or "Read the contents of a file in the repository.",
                "args_schema": ReadFileModel,
            },
            {
                "name": "update_file",
                "ref": self.update_file,
                "description": self.update_file.__doc__ or "Update the contents of a file in the repository.",
                "args_schema": UpdateFileModel,
            },
            {
                "name": "set_active_branch",
                "ref": self.set_active_branch,
                "description": self.set_active_branch.__doc__ or "Set the active branch in the repository.",
                "args_schema": SetActiveBranchModel,
            },
            {
                "name": "get_pull_requests_commits",
                "ref": self.get_pull_requests_commits,
                "description": self.get_pull_requests_commits.__doc__ or "Get commits from a pull request in the repository.",
                "args_schema": GetPullRequestsCommitsModel,
            },
            {
                "name": "get_pull_request",
                "ref": self.get_pull_request,
                "description": self.get_pull_request.__doc__ or "Get details of a pull request in the repository.",
                "args_schema": GetPullRequestModel,
            },
            {
                "name": "get_pull_requests_changes",
                "ref": self.get_pull_requests_changes,
                "description": self.get_pull_requests_changes.__doc__ or "Get changes from a pull request in the repository.",
                "args_schema": GetPullRequestsChangesModel,
            },
            {
                "name": "add_pull_request_comment",
                "ref": self.add_pull_request_comment,
                "description": self.add_pull_request_comment.__doc__ or "Add a comment to a pull request in the repository.",
                "args_schema": AddPullRequestCommentModel,
            }
        ]