from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, List

from atlassian.bitbucket import Bitbucket, Cloud
from langchain_core.tools import ToolException
from requests import Response
from ..ado.utils import extract_old_new_pairs

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

if TYPE_CHECKING:
    pass


def normalize_response(response) -> Dict[str, Any]:
    """
    Normalize API response to dictionary format.
    Handles different response types from Bitbucket APIs.
    """
    if isinstance(response, dict):
        return response
    if hasattr(response, 'to_dict'):
        return response.to_dict()
    if hasattr(response, '__dict__'):
        return {k: v for k, v in response.__dict__.items()
                if isinstance(v, (str, int, float, bool, list, dict, type(None)))}
    return {"raw_response": str(response)}


class BitbucketApiAbstract(ABC):

    @abstractmethod
    def list_branches(self) -> List[str]:
        pass

    @abstractmethod
    def create_branch(self, branch_name: str, branch_from: str) -> Response:
        pass

    @abstractmethod
    def create_pull_request(self, pr_json_data: str) -> Any:
        pass

    @abstractmethod
    def get_file(self, file_path: str, branch: str) -> str:
        pass

    @abstractmethod
    def get_files_list(self, file_path: str, branch: str) -> str:
        pass

    @abstractmethod
    def create_file(self, file_path: str, file_contents: str, branch: str) -> str:
        pass

    @abstractmethod
    def get_pull_request_commits(self, pr_id: str) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_pull_request(self, pr_id: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_pull_requests_changes(self, pr_id: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    def add_pull_request_comment(self, pr_id: str, text: str) -> str:
        pass


class BitbucketServerApi(BitbucketApiAbstract):
    api_client: Bitbucket

    def __init__(self, url, project, repository, username, password):
        self.url = url
        self.project = project
        self.repository = repository
        self.username = username
        self.password = password
        self.api_client = Bitbucket(url=url, username=username, password=password)

    def list_branches(self) -> List[str]:
        branches = self.api_client.get_branches(project_key=self.project, repository_slug=self.repository)
        return [branch['displayId'] for branch in branches]

    def create_branch(self, branch_name: str, branch_from: str) -> Response:
        return self.api_client.create_branch(
            self.project,
            self.repository,
            branch_name,
            branch_from
        )

    def create_pull_request(self, pr_json_data: str) -> Any:
        return self.api_client.create_pull_request(project_key=self.project,
                                                   repository_slug=self.repository,
                                                   data=json.loads(pr_json_data)
                                                   )

    # TODO: review this method, it may not work as expected
    def get_file_commit_hash(self, file_path: str, branch: str):
        """
        Get the commit hash of a file in a specific branch.
        Parameters:
            file_path (str): The path to the file.
            branch (str): The branch name.
        Returns:
            str: The commit hash of the file.
        """
        commits = self.api_client.get_commits(project_key=self.project, repository_slug=self.repository,
                                              filename=file_path, at=branch, limit=1)
        if commits:
            return commits[0]['id']
        return None

    def get_file(self, file_path: str, branch: str) -> str:
        return self.api_client.get_content_of_file(project_key=self.project, repository_slug=self.repository, at=branch,
                                                   filename=file_path).decode('utf-8')

    def get_files_list(self, file_path: str, branch: str) -> list:
        files = self.api_client.get_file_list(project_key=self.project, repository_slug=self.repository, query=branch,
                                              sub_folder=file_path)
        files_list = []
        for file in files:
            files_list.append(file['path'])
        return files_list

    def create_file(self, file_path: str, file_contents: str, branch: str) -> str:
        return self.api_client.upload_file(
            project_key=self.project,
            repository_slug=self.repository,
            content=file_contents,
            message=f"Create {file_path}",
            branch=branch,
            filename=file_path
        )

    def update_file(self, file_path: str, update_query: str, branch: str) -> str:
        file_content = self.get_file(file_path=file_path, branch=branch)
        updated_file_content = file_content
        for old, new in extract_old_new_pairs(update_query):
            if not old.strip():
                continue
            updated_file_content = updated_file_content.replace(old, new)

        if file_content == updated_file_content:
            raise ToolException(
                "File content was not updated because old content was not found or empty. "
                "It may be helpful to use the read_file action to get "
                "the current file contents."
            )

        source_commit_generator = self.api_client.get_commits(project_key=self.project, repository_slug=self.repository,
                                                              hash_newest=branch, limit=1)
        source_commit = next(source_commit_generator)
        return self.api_client.update_file(
            project_key=self.project,
            repository_slug=self.repository,
            content=updated_file_content,
            message=f"Update {file_path}",
            branch=branch,
            filename=file_path,
            source_commit_id=source_commit['id']
        )

    def get_pull_request_commits(self, pr_id: str) -> List[Dict[str, Any]]:
        """
        Get commits from a pull request
        Parameters:
            pr_id(str): the pull request ID
        Returns:
            List[Dict[str, Any]]: List of commits in the pull request
        """
        return self.api_client.get_pull_requests_commits(project_key=self.project, repository_slug=self.repository,
                                                         pull_request_id=pr_id)

    def get_pull_request(self, pr_id):
        """ Get details of a pull request
        Parameters:
            pr_id(str): the pull request ID
        Returns:
            Dict[str, Any]: Details of the pull request
        """
        response = self.api_client.get_pull_request(project_key=self.project, repository_slug=self.repository,
                                                    pull_request_id=pr_id)
        return normalize_response(response)

    def get_pull_requests_changes(self, pr_id: str) -> Dict[str, Any]:
        """
        Get changes of a pull request
        Parameters:
            pr_id(str): the pull request ID
        Returns:
            Dict[str, Any]: Changes of the pull request
        """
        response = self.api_client.get_pull_requests_changes(project_key=self.project, repository_slug=self.repository,
                                                             pull_request_id=pr_id)
        return normalize_response(response)

    def add_pull_request_comment(self, pr_id, content, inline=None):
        """
        Add a comment to a pull request. Supports multiple content types and inline comments.
        Parameters:
            pr_id (str): the pull request ID
            content (dict or str): The comment content. If str, will be used as raw text. If dict, can include 'raw', 'markup', 'html'.
            inline (dict, optional): Inline comment details. Example: {"from": 57, "to": 122, "path": "<string>"}
        Returns:
            str: The API response or created comment URL
        """
        # Build the comment data
        if isinstance(content, str):
            comment_data = {"text": content}
        elif isinstance(content, dict):
            # Bitbucket Server API expects 'text' (raw), and optionally 'markup' and 'html' in a 'content' field
            if 'raw' in content or 'markup' in content or 'html' in content:
                comment_data = {"text": content.get("raw", "")}
                if 'markup' in content:
                    comment_data["markup"] = content["markup"]
                if 'html' in content:
                    comment_data["html"] = content["html"]
            else:
                comment_data = {"text": str(content)}
        else:
            comment_data = {"text": str(content)}

        if inline:
            comment_data["inline"] = inline

        return self.api_client.add_pull_request_comment(
            project_key=self.project,
            repository_slug=self.repository,
            pull_request_id=pr_id,
            **comment_data
        )


class BitbucketCloudApi(BitbucketApiAbstract):
    api_client: Cloud

    def __init__(self, url, workspace, repository, username, password):
        self.url = url
        self.workspace_name = workspace
        self.repository_name = repository
        self.username = username
        self.password = password
        self.api_client = Cloud(url=url, username=username, password=password)
        self.workspace = self.api_client.workspaces.get(self.workspace_name)
        try:
            self.repository = self.workspace.repositories.get(self.repository_name)
        except Exception as e:
            raise ToolException(f"Unable to connect to the repository '{self.repository_name}' due to error:\n{str(e)}")

    def list_branches(self) -> List[str]:
        branches = self.repository.branches.each()
        branch_names = [branch.name for branch in branches]
        return branch_names

    def _get_branch(self, branch_name: str) -> Response:
        return self.repository.branches.get(branch_name)

    def create_branch(self, branch_name: str, branch_from: str) -> Response:
        """
        Creates new branch from last commit branch
        """
        logger.info(f"Create new branch from '{branch_from}")
        commits_name = self._get_branch(branch_from).hash
        # create new branch from last commit
        return self.repository.branches.create(branch_name, commits_name)

    def create_pull_request(self, pr_json_data: str) -> Any:
        response = self.repository.pullrequests.post(None, data=json.loads(pr_json_data))
        return response['links']['self']['href']

    # TODO: review this method, it may not work as expected
    def get_file_commit_hash(self, file_path: str, branch: str):
        """
        Get the commit hash of a file in a specific branch.
        Parameters:
            file_path (str): The path to the file.
            branch (str): The branch name.
        Returns:
            str: The commit hash of the file.
        """
        commits = self.repository.commits.get(path=file_path, branch=branch, pagelen=1)
        if commits['values']:
            return commits['values'][0]['hash']
        return None

    def get_file(self, file_path: str, branch: str) -> str:
        return self.repository.get(path=f'src/{branch}/{file_path}')

    def get_files_list(self, file_path: str, branch: str) -> list:
        files_list = []
        index = 0
        # TODO: add pagination
        for item in \
                self.repository.get(
                    path=f'src/{branch}/{file_path}?max_depth=100&pagelen=100&fields=values.path&q=type="commit_file"')[
                    'values']:
            files_list.append(item['path'])
        return files_list

    def create_file(self, file_path: str, file_contents: str, branch: str) -> str:
        form_data = {
            'branch': f'{branch}',
            f'{file_path}': f'{file_contents}',
        }
        return self.repository.post(path='src', data=form_data, files={},
                                    headers={'Content-Type': 'application/x-www-form-urlencoded'})

    def update_file(self, file_path: str, update_query: str, branch: str) -> ToolException | str:

        file_content = self.get_file(file_path=file_path, branch=branch)
        updated_file_content = file_content
        for old, new in extract_old_new_pairs(file_query=update_query):
            if not old.strip():
                continue
            updated_file_content = updated_file_content.replace(old, new)

        if file_content == updated_file_content:
            return ToolException(
                "File content was not updated because old content was not found or empty. "
                "It may be helpful to use the read_file action to get "
                "the current file contents."
            )
        return self.create_file(file_path, updated_file_content, branch)

    def get_pull_request_commits(self, pr_id: str) -> List[Dict[str, Any]]:
        """
        Get commits from a pull request
        Parameters:
            pr_id(str): the pull request ID
        Returns:
            List[Dict[str, Any]]: List of commits in the pull request
        """
        return self.repository.pullrequests.get(pr_id).get('commits', {}).get('values', [])

    def get_pull_request(self, pr_id: str) -> Dict[str, Any]:
        """ Get details of a pull request
        Parameters:
            pr_id(str): the pull request ID
        Returns:
            Dict[str, Any]: Details of the pull request
        """
        response = self.repository.pullrequests.get(pr_id)
        return normalize_response(response)

    def get_pull_requests_changes(self, pr_id: str) -> Dict[str, Any]:
        """
        Get changes of a pull request
        Parameters:
            pr_id(str): the pull request ID
        Returns:
            Dict[str, Any]: Changes of the pull request
        """
        response = self.repository.pullrequests.get(pr_id).get('diff', {})
        return normalize_response(response)

    def add_pull_request_comment(self, pr_id: str, content, inline=None) -> str:
        """
        Add a comment to a pull request. Supports multiple content types and inline comments.
        Parameters:
            pr_id (str): the pull request ID
            content (dict or str): The comment content. If str, will be used as raw text. If dict, can include 'raw', 'markup', 'html'.
            inline (dict, optional): Inline comment details. Example: {"from": 57, "to": 122, "path": "<string>"}
        Returns:
            str: The URL of the created comment
        """
        # Build the content dict for Bitbucket Cloud
        if isinstance(content, str):
            content_dict = {"raw": content}
        elif isinstance(content, dict):
            # Only include allowed keys
            content_dict = {k: v for k, v in content.items() if k in ("raw", "markup", "html")}
            if not content_dict:
                content_dict = {"raw": str(content)}
        else:
            content_dict = {"raw": str(content)}

        data = {"content": content_dict}
        if inline:
            data["inline"] = inline

        response = self.repository.pullrequests.get(pr_id).post("comments", data)
        return response['links']['html']['href']