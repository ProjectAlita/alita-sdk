# import logging
# import traceback
# from typing import Type, Optional
#
# from .api_wrapper import (
#     GitLabAPIWrapper,
#     CreateBranchInput,
#     CreatePRInput,
#     DeleteFileInput,
#     CreateFileInput,
#     SetActiveBranchInput,
#     ReadFileInput,
#     UpdateFileInput,
#     AppendFileInput,
#     ListFilesInput,
#     ListFoldersInput,
#     GetPRChangesInput,
#     CreatePRChangeCommentInput,
#     GetCommitsInput
# )
# from langchain_core.tools import BaseTool, ToolException
# from pydantic.fields import Field
# from pydantic import create_model, BaseModel
# from gitlab.exceptions import GitlabGetError
#
# from .utils import get_diff_w_position, get_position
#
# logger = logging.getLogger(__name__)
#
# UPDATE_FILE_PROMPT = """Updates the contents of a file in a repository. Your input MUST strictly follow these rules:
# Specify which file to modify passing a full file path (the path must not start with a slash); Specify at least 2 lines of the old contents which you would like to replace wrapped in OLD <<<< and >>>> OLD; Specify the new contents which you would like to replace the old contents with wrapped in NEW <<<< and >>>> NEW; NEW content may contain lines from OLD content in case you want to add content without removing the old content
#
# Example 1: Replace "old contents" to "new contents" in the file /test/test.txt from , pass in the following string:
#
# test/test.txt
#
# This is text that will not be changed
# OLD <<<<
# old contents
# >>>> OLD
# NEW <<<<
# new contents
# >>>> NEW
#
# Example 2: Extend "existing contents" with new contents" in the file /test/test.txt, pass in the following string:
#
# test/test.txt
#
# OLD <<<<
# existing contents
# >>>> OLD
# NEW <<<<
# existing contents
# new contents
# >>>> NEW"""
#
# branch_description: str = "The name of the branch required to perform corresponding action. e.g. `feature-1`. **IMPORTANT**: if branch not specified, try to determine from the chat history or clarify with user."
#
# branchInput = create_model(
#     "BranchInput",
#     branch_name=(str, Field(description="The name of the branch, e.g. `my_branch`.")))
#
# class CreateGitLabBranchTool(BaseTool):
#
#     api_wrapper: GitLabAPIWrapper = Field(default_factory=GitLabAPIWrapper)
#     name: str = "create_branch"
#     description: str = """This tool is a wrapper for the GitLab API to create a new branch in the repository."""
#     args_schema: Type[BaseModel] = CreateBranchInput
#
#     def _run(self, branch_name: str):
#         try:
#             logger.info(f"Creating branch {branch_name} in the repository.")
#             return self.api_wrapper.create_branch(branch_name)
#         except Exception as e:
#             stacktrace = traceback.format_exc()
#             logger.error(f"Unable to create a branch: {stacktrace}")
#             return f"Unable to create a branch: {stacktrace}"
#
# class CreatePRTool(BaseTool):
#     api_wrapper: GitLabAPIWrapper = Field(default_factory=GitLabAPIWrapper)
#     name: str = "create_pull_request"
#     description: str = """This tool is a wrapper for the GitLab API to create a new pull request in a GitLab repository.
#     Strictly follow and provide input parameters based on context.
#     """
#     args_schema: Type[BaseModel] = CreatePRInput
#
#     def _run(self, pr_title: str, pr_body: str, branch: str):
#         try:
#             base_branch = self.api_wrapper.branch
#             logger.info(f"Creating pull request with title: {pr_title}, body: {pr_body}, base_branch: {base_branch}")
#             return self.api_wrapper.create_pull_request(pr_title, pr_body, branch)
#         except Exception as e:
#             stacktrace = traceback.format_exc()
#             logger.error(f"Unable to create PR: {stacktrace}")
#             return f"Unable to create PR: {stacktrace}"
#
#
# class DeleteFileTool(BaseTool):
#     api_wrapper: GitLabAPIWrapper = Field(default_factory=GitLabAPIWrapper)
#     name: str = "delete_file"
#     description: str = """This tool is a wrapper for the GitLab API, useful when you need to delete a file in a GitLab repository.
#     Simply pass in the full file path of the file you would like to delete. **IMPORTANT**: the path must not start with a slash"""
#     args_schema: Type[BaseModel] = DeleteFileInput
#
#     def _run(self, file_path: str, branch: str):
#         try:
#             return self.api_wrapper.delete_file(file_path, branch)
#         except Exception as e:
#             stacktrace = traceback.format_exc()
#             logger.error(f"Unable to delete file: {stacktrace}")
#             return f"Unable to delete file: {stacktrace}"
#
# class CreateFileTool(BaseTool):
#     api_wrapper: GitLabAPIWrapper = Field(default_factory=GitLabAPIWrapper)
#     name: str = "create_file"
#     description: str = """This tool is a wrapper for the GitLab API, useful when you need to create a file in a GitLab repository.
#     """
#     args_schema: Type[BaseModel] = CreateFileInput
#
#     def _run(self, file_path: str, file_contents: str, branch: str):
#         logger.info(f"Create file in the repository {file_path} with content: {file_contents}")
#         return self.api_wrapper.create_file(file_path, file_contents, branch)
#
#
# class SetActiveBranchTool(BaseTool):
#     api_wrapper: GitLabAPIWrapper = Field(default_factory=GitLabAPIWrapper)
#     name: str = "set_active_branch"
#     description: str = """
#     This tool is a wrapper for the Git API and set the active branch in the repository, similar to `git checkout <branch_name>` and `git switch -c <branch_name>`."""
#     args_schema: Type[BaseModel] = SetActiveBranchInput
#
#     def _run(self, branch_name: str):
#         try:
#             logger.info(f"Set active branch {branch_name} in the repository.")
#             return self.api_wrapper.set_active_branch(branch=branch_name)
#         except Exception as e:
#             stacktrace = traceback.format_exc()
#             logger.error(f"Unable to set active branch: {stacktrace}")
#             return f"Unable to set active branch: {stacktrace}"
#
# class ListBranchesTool(BaseTool):
#     """Tool for interacting with the GitHub API."""
#
#     api_wrapper: GitLabAPIWrapper = Field(default_factory=GitLabAPIWrapper)
#     name: str = "list_branches_in_repo"
#     description: str = """This tool is a wrapper for the Git API to fetch a list of all branches in the repository.
#     It will return the name of each branch. No input parameters are required."""
#     args_schema: Type[BaseModel] = None
#
#     def _run(self):
#         try:
#             logger.debug(f"List branches in the repository.")
#             return self.api_wrapper.list_branches_in_repo()
#         except Exception as e:
#             stacktrace = traceback.format_exc()
#             logger.error(f"Unable to list branches: {stacktrace}")
#             return f"Unable to list branches: {stacktrace}"
#
#
# class GetPullRequesChanges(BaseTool):
#     api_wrapper: GitLabAPIWrapper = Field(default_factory=GitLabAPIWrapper)
#     name: str = "get_pr_changes"
#     description: str = """This tool is a wrapper for the GitLab API, useful when you need to get all the changes from pull request in git diff format with added line numbers.
#     """
#     args_schema: Type[BaseModel] = GetPRChangesInput
#     handle_tool_error: bool = True
#
#     def _run(self, pr_number: int):
#         try:
#             repo = self.api_wrapper._repo_instance
#             try:
#                 mr = repo.mergerequests.get(pr_number)
#             except GitlabGetError as e:
#                 if e.response_code == 404:
#                     raise ToolException(f"Merge request number {pr_number} wasn't found: {e}")
#
#             res = f"""title: {mr.title}\ndescription: {mr.description}\n\n"""
#
#             for change in mr.changes()["changes"]:
#                 diff_w_position = get_diff_w_position(change=change)
#                 diff = "\n".join([str(line_num) + ":" + line[1] for line_num, line in diff_w_position.items()])
#
#                 res = res + f"""diff --git a/{change["old_path"]} b/{change["new_path"]}\n{diff}\n"""
#
#             return res
#         except ToolException as te:
#             raise
#         except Exception as e:
#             raise ToolException(f"An error occurred: {e}")
#
#
# class CreatePullRequestChangeCommentInput(BaseModel):
#     pr_number: int = Field(description="""GitLab Merge Request (Pull Request) number""")
#     file_path: str = Field(description="""File path of the changed file""")
#     line_number: int = Field(description="""Line number from the diff for a changed file""")
#     comment: str = Field(description="""Comment content""")
#
#
# class CreatePullRequestChangeComment(BaseTool):
#     api_wrapper: GitLabAPIWrapper = Field(default_factory=GitLabAPIWrapper)
#     name: str = "create_pr_change_comment"
#     description: str = """This tool is a wrapper for the GitLab API, useful when you need to create a comment on a pull request change.
#     """
#     args_schema: Type[BaseModel] = CreatePRChangeCommentInput
#     handle_tool_error: bool = True
#
#     def _run(self, pr_number: int, file_path: str, line_number: int, comment: str, *args):
#         if line_number == 0:
#             raise ToolException("Line number for comment must be greater than 0")
#         repo = self.api_wrapper._repo_instance
#         try:
#             mr = repo.mergerequests.get(pr_number)
#         except GitlabGetError as e:
#             if e.response_code == 404:
#                 raise ToolException(f"Merge request number {pr_number} wasn't found: {e}")
#         try:
#             position = get_position(file_path=file_path, line_number=line_number, mr=mr)
#
#             mr.discussions.create({"body": comment, "position": position})
#             return "Comment added"
#         except Exception as e:
#             raise ToolException(f"An error occurred: {e}")
#
#
#
# class UpdateFileToolModel(BaseModel):
#     file_query: str = Field(description="Strictly follow the provided rules.")
#     branch: str = Field(description=branch_description)
#
# class AppendFileToolModel(BaseModel):
#     file_path: str = Field(description="Path to the file new content will be appended to.")
#     content: str = Field(description="Content to be added to the file.")
#     branch: str = Field(description=branch_description)
#
# class ListFilesModel(BaseModel):
#     path: Optional[str] = Field(description="Repository path/package to extract files from.", default=None)
#     recursive: Optional[bool] = Field(description="Return files list recursively. Default: True", default=True)
#     branch: Optional[str] = Field(description="Repository branch.", default=None)
#
# class ListFilesTool(BaseTool):
#     api_wrapper: GitLabAPIWrapper = Field(default_factory=GitLabAPIWrapper)
#     name: str = "list_files"
#     description: str = "Lists files per defined path and branch"
#     args_schema: Type[BaseModel] = ListFilesInput
#     handle_tool_error: bool = True
#
#     def _run(self, path: str = None, recursive: bool = True, branch: str = None):
#         try:
#             return self.api_wrapper.list_files(path, recursive, branch)
#         except Exception as e:
#             stacktrace = traceback.format_exc()
#             logger.error(f"Unable to update file: {stacktrace}")
#             raise ToolException(f"Unable to update file: {stacktrace}")
#
# class ListFoldersModel(BaseModel):
#     path: Optional[str] = Field(description="Repository path/package to extract folders from.", default=None)
#     recursive: Optional[bool] = Field(description="Return folders list recursively. Default: True", default=True)
#     branch: Optional[str] = Field(description="Repository branch.", default=None)
#
# class ListFoldersTool(BaseTool):
#     api_wrapper: GitLabAPIWrapper = Field(default_factory=GitLabAPIWrapper)
#     name: str = "list_folders"
#     description: str = "Lists folders per defined path and branch"
#     args_schema: Type[BaseModel] = ListFoldersInput
#     handle_tool_error: bool = True
#
#     def _run(self, path: str = None, recursive: bool = True, branch: str = None):
#         try:
#             return self.api_wrapper.list_folders(path, recursive, branch)
#         except Exception as e:
#             stacktrace = traceback.format_exc()
#             logger.error(f"Unable to extract folders: {stacktrace}")
#             raise ToolException(f"Unable to extract folders: {stacktrace}")
#
# class UpdateFileTool(BaseTool):
#     api_wrapper: GitLabAPIWrapper = Field(default_factory=GitLabAPIWrapper)
#     name: str = "update_file"
#     description: str = UPDATE_FILE_PROMPT
#     args_schema: Type[BaseModel] = UpdateFileInput
#     handle_tool_error: bool = True
#
#     def _run(self, file_query: str, branch: str):
#         try:
#             return self.api_wrapper.update_file(file_query, branch)
#         except Exception as e:
#             stacktrace = traceback.format_exc()
#             logger.error(f"Unable to update file: {stacktrace}")
#             raise ToolException(f"Unable to update file: {stacktrace}")
#
# class AppendFileTool(BaseTool):
#     api_wrapper: GitLabAPIWrapper = Field(default_factory=GitLabAPIWrapper)
#     name: str = "append_file"
#     description: str = """Append Tool used for adding of new content to the end of existing file.
#                         Useful in case file content is greater than model's output tokens"""
#     args_schema: Type[BaseModel] = AppendFileInput
#
#     def _run(self, file_path: str, content: str, branch: str):
#         try:
#             return self.api_wrapper.append_file(file_path, content, branch)
#         except Exception:
#             stacktrace = traceback.format_exc()
#             logger.error(f"Unable to append to the file: {stacktrace}")
#             raise ToolException(f"Unable to append to the file: {stacktrace}")
#
# class ReadFileTool(BaseTool):
#     api_wrapper: GitLabAPIWrapper = Field(default_factory=GitLabAPIWrapper)
#     name: str = "read_file"
#     description: str = """This tool is a wrapper for the GitLab API, useful when you need to read a file in a GitLab repository.
#     Simply pass in the full
#     file path of the file you would like to read. **IMPORTANT**: the path must not start with a slash"""
#     args_schema: Type[BaseModel] = ReadFileInput
#
#     def _run(self, file_path: str, branch: str):
#         try:
#             return self.api_wrapper.read_file(file_path, branch)
#         except Exception as e:
#             stacktrace = traceback.format_exc()
#             logger.error(f"Unable to read file: {stacktrace}")
#             return f"Unable to read file: {stacktrace}"
#
# class GetCommitsTool(BaseTool):
#     api_wrapper: GitLabAPIWrapper = Field(default_factory=GitLabAPIWrapper)
#     name: str = "get_commits"
#     description: str = """This tool is a wrapper for the GitLab API, useful when you need to retrieve a list of commits from the repository."""
#     args_schema: Type[BaseModel] = GetCommitsInput
#
#     def _run(self, sha: Optional[str] = None,
#             path: Optional[str] = None,
#             since: Optional[str] = None,
#             until: Optional[str] = None,
#             author: Optional[str] = None):
#         try:
#             return self.api_wrapper.get_commits(sha, path, since, until, author)
#         except Exception as e:
#             stacktrace = traceback.format_exc()
#             logger.error(f"Unable to get commits: {stacktrace}")
#             return f"Unable to get commits: {stacktrace}"
#
# __all__ = [
#     {"name": "create_branch", "tool": CreateGitLabBranchTool},
#     {"name": "create_pull_request", "tool": CreatePRTool},
#     {"name": "delete_file", "tool": DeleteFileTool},
#     {"name": "create_file", "tool": CreateFileTool},
#     {"name": "update_file", "tool": UpdateFileTool},
#     {"name": "append_file", "tool": AppendFileTool},
#     {"name": "list_files", "tool": ListFilesTool},
#     {"name": "list_folders", "tool": ListFoldersTool},
#     {"name": "set_active_branch", "tool": SetActiveBranchTool},
#     {"name": "list_branches_in_repo", "tool": ListBranchesTool},
#     {"name": "get_pr_changes", "tool": GetPullRequesChanges},
#     {"name": "create_pr_change_comment", "tool": CreatePullRequestChangeComment},
#     {"name": "read_file", "tool": ReadFileTool},
#     {"name": "get_commits", "tool": GetCommitsTool}
# ]