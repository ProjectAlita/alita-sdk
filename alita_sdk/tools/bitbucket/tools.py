import logging
import traceback
from typing import Type, Optional, List

from langchain_core.tools import BaseTool
from pydantic import create_model, Field, BaseModel
from .bitbucket_constants import create_pr_data

from .api_wrapper import BitbucketAPIWrapper
from ..elitea_base import LoaderSchema

logger = logging.getLogger(__name__)

branchInput = create_model(
    "BranchInput",
    branch_name=(str, Field(description="The name of the branch, e.g. `my_branch`.")))


class CreateBitbucketBranchTool(BaseTool):
    api_wrapper: BitbucketAPIWrapper = Field(default_factory=BitbucketAPIWrapper)
    name: str = "create_branch"
    description: str = """This tool is a wrapper for the Bitbucket API to create a new branch in the repository."""
    args_schema: Type[BaseModel] = branchInput

    def _run(self, branch_name: str):
        try:
            logger.info(f"Creating branch {branch_name} in the repository.")
            return self.api_wrapper.create_branch(branch_name)
        except Exception:
            stacktrace = traceback.format_exc()
            logger.error(f"Unable to create a branch: {stacktrace}")
            return f"Unable to create a branch: {stacktrace}"


class CreatePRTool(BaseTool):
    api_wrapper: BitbucketAPIWrapper = Field(default_factory=BitbucketAPIWrapper)
    name: str = "create_pull_request"
    description: str = """This tool is a wrapper for the Bitbucket API to create a new pull request in a GitLab repository.
    Strictly follow and provide input parameters based on context.
    """
    args_schema: Type[BaseModel] = create_model(
        "CreatePRInput",
        pr_json_data=(str, Field(description=create_pr_data)))

    def _run(self, pr_json_data: str):
        try:
            base_branch = self.api_wrapper.branch
            logger.info(f"Creating pull request using data: base_branch: {pr_json_data}")
            return self.api_wrapper.create_pull_request(pr_json_data)
        except Exception as e:
            stacktrace = traceback.format_exc()
            logger.error(f"Unable to create PR: {stacktrace}")
            return f"Unable to create PR: {stacktrace}"


class CreateFileTool(BaseTool):
    api_wrapper: BitbucketAPIWrapper = Field(default_factory=BitbucketAPIWrapper)
    name: str = "create_file"
    description: str = """This tool is a wrapper for the Bitbucket API, useful when you need to create a file in a Bitbucket repository.
    """
    args_schema: Type[BaseModel] = create_model(
        "CreateFileInput",
        file_path=(str, Field(
            description="File path of file to be created. e.g. `src/agents/developer/tools/git/bitbucket.py`. **IMPORTANT**: the path must not start with a slash")),
        file_contents=(str, Field(description="""
    Full file content to be created. It must be without any escapes, just raw content to CREATE in GIT.
    Generate full file content for this field without any additional texts, escapes, just raw code content. 
    You MUST NOT ignore, skip or comment any details, PROVIDE FULL CONTENT including all content based on all best practices.
    """)),
        branch=(str, Field(
            description="branch - name of the branch file should be read from. e.g. `feature-1`. **IMPORTANT**: if branch not specified, try to determine from the chat history or clarify with user."))
    )

    def _run(self, file_path: str, file_contents: str, branch: str):
        logger.info(f"Create file in the repository {file_path} with content: {file_contents}")
        return self.api_wrapper.create_file(file_path, file_contents, branch)


class UpdateFileTool(BaseTool):
    api_wrapper: BitbucketAPIWrapper = Field(default_factory=BitbucketAPIWrapper)
    name: str = "update_file"
    description: str = """
        Updates a file with new content.
        Parameters:
            file_path (str): Path to the file to be updated 
            branch (str): The name of the branch where update the file.
            update_query(str): Contains file contents.
                The old file contents is wrapped in OLD <<<< and >>>> OLD
                The new file contents is wrapped in NEW <<<< and >>>> NEW
                For example:
                /test/hello.txt
                OLD <<<<
                Hello Earth!
                >>>> OLD
                NEW <<<<
                Hello Mars!
                >>>> NEW
                """
    args_schema: Type[BaseModel] = create_model(
        "UpdateFileTool",
        file_path=(str, Field(
            description="File path of file to be updated. e.g. `src/agents/developer/tools/git/bitbucket.py`. **IMPORTANT**: the path must not start with a slash")),
        update_query=(str, Field(description="File path followed by the old and new contents")),
        branch=(str, Field(
            description="branch - the name of the branch where file that has to be updated is located. e.g. `feature-1`. **IMPORTANT**: if branch not specified, try to determine from the chat history or clarify with user."))
    )

    def _run(self, file_path: str, update_query: str, branch: str):
        logger.info(f"Update file in the repository {file_path} with content: {update_query} and branch {branch}")
        return self.api_wrapper.update_file(file_path, update_query, branch)


class SetActiveBranchTool(BaseTool):
    api_wrapper: BitbucketAPIWrapper = Field(default_factory=BitbucketAPIWrapper)
    name: str = "set_active_branch"
    description: str = """
    This tool is a wrapper for the Bitbucket API and set the active branch in the repository, similar to `git checkout <branch_name>` and `git switch -c <branch_name>`."""
    args_schema: Type[BaseModel] = branchInput

    def _run(self, branch_name: str):
        try:
            logger.info(f"Set active branch {branch_name} in the repository.")
            return self.api_wrapper.set_active_branch(branch=branch_name)
        except Exception as e:
            stacktrace = traceback.format_exc()
            logger.error(f"Unable to set active branch: {stacktrace}")
            return f"Unable to set active branch: {stacktrace}"


class ListBranchesTool(BaseTool):
    """Tool for interacting with the Bitbucket API."""

    api_wrapper: BitbucketAPIWrapper = Field(default_factory=BitbucketAPIWrapper)
    name: str = "list_branches_in_repo"
    description: str = """This tool is a wrapper for the Bitbucket API to fetch a list of all branches in the repository. 
    It will return the name of each branch. No input parameters are required."""
    args_schema: Type[BaseModel] = None

    def _run(self):
        try:
            logger.debug("List branches in the repository.")
            return self.api_wrapper.list_branches_in_repo()
        except Exception as e:
            stacktrace = traceback.format_exc()
            logger.error(f"Unable to list branches: {stacktrace}")
            return f"Unable to list branches: {stacktrace}"


class ReadFileTool(BaseTool):
    api_wrapper: BitbucketAPIWrapper = Field(default_factory=BitbucketAPIWrapper)
    name: str = "read_file"
    description: str = """This tool is a wrapper for the GitLab API, useful when you need to read a file in a GitLab repository.
    Simply pass in the full
    file path of the file you would like to read. **IMPORTANT**: the path must not start with a slash"""
    args_schema: Type[BaseModel] = create_model(
        "ReadFileInput",
        file_path=(str, Field(
            description="File path of file to be read. e.g. `src/agents/developer/tools/git/github_tools.py`. **IMPORTANT**: the path must not start with a slash")),
        branch=(str, Field(
            description="branch - name of the branch file should be read from. e.g. `feature-1`. **IMPORTANT**: if branch not specified, try to determine from the chat history or clarify with user."))
    )

    def _run(self, file_path: str, branch: str):
        try:
            return self.api_wrapper._read_file(file_path, branch)
        except Exception:
            stacktrace = traceback.format_exc()
            logger.error(f"Unable to read file: {stacktrace}")
            return f"Unable to read file: {stacktrace}"


class GetFilesListTool(BaseTool):
    api_wrapper: BitbucketAPIWrapper = Field(default_factory=BitbucketAPIWrapper)
    name: str = "get_files"
    description: str = """
    This tool returns list of files.
    IMPORTANT: *User may leave it empty if he wants to read files from the root of the repository and using active branch.*

    Args:
        file_path (Optional[str], default: None): Package path to read files from. e.g. `src/agents/developer/tools/git/`. **IMPORTANT**: the path must not start with a slash.
        branch (Optional[str], default: None): branch - name of the branch file should be read from. e.g. `feature-1`. **IMPORTANT**: if branch not specified, try to determine from the chat history, leave it empty.
    """
    args_schema: Type[BaseModel] = create_model(
        "GetFilesListModel",
        file_path=(Optional[str], Field(
            description="Package path to read files from. e.g. `src/agents/developer/tools/git/`. Default: None. "
                        "**IMPORTANT**: the path must not start with a slash",
            default=None)),
        branch=(Optional[str], Field(
            description="branch - name of the branch file should be read from. e.g. `feature-1`. Default: None. "
                        "**IMPORTANT**: if branch not specified, try to determine from the chat history or use active branch.",
            default=None))
    )

    def _run(self, file_path: Optional[str] = None, branch: Optional[str] = None):
        try:
            return self.api_wrapper._get_files(file_path, branch)
        except Exception:
            stacktrace = traceback.format_exc()
            logger.error(f"Unable to read file: {stacktrace}")
            return f"Unable to read file: {stacktrace}"


class LoaderTool(BaseTool):
    api_wrapper: BitbucketAPIWrapper = Field(default_factory=BitbucketAPIWrapper)
    name: str = "loader"
    description: str = """This tool is a wrapper for the Bitbucket API, useful when you need to create a file in a Bitbucket repository.
    """
    args_schema: Type[BaseModel] = LoaderSchema

    def _run(self,
             branch: Optional[str] = None,
             whitelist: Optional[List[str]] = None,
             blacklist: Optional[List[str]] = None):
        return self.api_wrapper.loader(branch, whitelist, blacklist)


class GetPullRequestsCommitsTool(BaseTool):
    api_wrapper: BitbucketAPIWrapper = Field(default_factory=BitbucketAPIWrapper)
    name: str = "get_pull_requests_commits"
    description: str = """This tool is a wrapper for the Bitbucket API to get commits from pull requests."""
    args_schema: Type[BaseModel] = create_model(
        "GetPullRequestsCommitsInput",
        pr_id=(str, Field(description="The ID of the pull request to get commits from.")))

    def _run(self, pr_id: str):
        try:
            logger.debug(f"Get pull request commits for {pr_id}.")
            return self.api_wrapper.get_pull_requests_commits(pr_id)
        except Exception as e:
            stacktrace = traceback.format_exc()
            logger.error(f"Can't get commits from pull request `{pr_id}` due to error:\n{stacktrace}")
            return f"Can't get commits from pull request `{pr_id}` due to error:\n{stacktrace}"

class GetPullRequestTool(BaseTool):
    api_wrapper: BitbucketAPIWrapper = Field(default_factory=BitbucketAPIWrapper)
    name: str = "get_pull_request"
    description: str = """This tool is a wrapper for the Bitbucket API to get details of a pull request."""
    args_schema: Type[BaseModel] = create_model(
        "GetPullRequestInput",
        pr_id=(str, Field(description="The ID of the pull request to get details from.")))

    def _run(self, pr_id: str):
        try:
            logger.debug(f"Get pull request details for {pr_id}.")
            return self.api_wrapper.get_pull_request(pr_id)
        except Exception as e:
            stacktrace = traceback.format_exc()
            logger.error(f"Can't get pull request `{pr_id}` due to error:\n{stacktrace}")
            return f"Can't get pull request `{pr_id}` due to error:\n{stacktrace}"

class GetPullRequestsChangesTool(BaseTool):
    api_wrapper: BitbucketAPIWrapper = Field(default_factory=BitbucketAPIWrapper)
    name: str = "get_pull_requests_changes"
    description: str = """This tool is a wrapper for the Bitbucket API to get changes of a pull request."""
    args_schema: Type[BaseModel] = create_model(
        "GetPullRequestsChangesInput",
        pr_id=(str, Field(description="The ID of the pull request to get changes from.")))

    def _run(self, pr_id: str):
        try:
            logger.debug(f"Get pull request changes for {pr_id}.")
            return self.api_wrapper.get_pull_requests_changes(pr_id)
        except Exception as e:
            stacktrace = traceback.format_exc()
            logger.error(f"Can't get changes from pull request `{pr_id}` due to error:\n{stacktrace}")
            return f"Can't get changes from pull request `{pr_id}` due to error:\n{stacktrace}"

class AddPullRequestCommentTool(BaseTool):
    api_wrapper: BitbucketAPIWrapper = Field(default_factory=BitbucketAPIWrapper)
    name: str = "add_pull_request_comment"
    description: str = """This tool is a wrapper for the Bitbucket API to add a comment to a pull request.
    Supports multiple content types and inline comments."""
    args_schema: Type[BaseModel] = create_model(
        "AddPullRequestCommentInput",
        pr_id=(str, Field(description="The ID of the pull request to add a comment to.")),
        content=(str, Field(description="The comment content. Can be a string (raw text) or a dict with keys 'raw', 'markup', 'html'.")),
        inline=(Optional[dict], Field(default=None, description="Inline comment details. Example: {'from': 57, 'to': 122, 'path': '<string>'}"))
    )

    def _run(self, pr_id: str, content: str, inline: Optional[dict] = None):
        try:
            logger.debug(f"Add comment to pull request {pr_id}.")
            return self.api_wrapper.add_pull_request_comment(pr_id, content, inline)
        except Exception as e:
            stacktrace = traceback.format_exc()
            logger.error(f"Can't add comment to pull request `{pr_id}` due to error:\n{stacktrace}")
            return f"Can't add comment to pull request `{pr_id}` due to error:\n{stacktrace}"

__all__ = [
    {"name": "create_branch", "tool": CreateBitbucketBranchTool},
    {"name": "create_pull_request", "tool": CreatePRTool},
    {"name": "create_file", "tool": CreateFileTool},
    {"name": "set_active_branch", "tool": SetActiveBranchTool},
    {"name": "list_branches_in_repo", "tool": ListBranchesTool},
    {"name": "read_file", "tool": ReadFileTool},
    {"name": "get_files", "tool": GetFilesListTool},
    {"name": "update_file", "tool": UpdateFileTool},
    {"name": "loader", "tool": LoaderTool},
    {"name": "get_pull_requests_commits", "tool": GetPullRequestsCommitsTool},
    {"name": "get_pull_request", "tool": GetPullRequestTool},
    {"name": "get_pull_requests_changes", "tool": GetPullRequestsChangesTool},
    {"name": "add_pull_request_comment", "tool": AddPullRequestCommentTool}
]
