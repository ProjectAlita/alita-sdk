import logging
from datetime import datetime
from typing import Optional, Any, List, Dict
import fnmatch

from gitlab import GitlabGetError
from langchain_core.tools import ToolException
from pydantic import model_validator, PrivateAttr, create_model, SecretStr
from pydantic.fields import Field

from ..elitea_base import BaseToolApiWrapper, BaseCodeToolApiWrapper
from ..gitlab.utils import get_diff_w_position, get_position
from ..utils.tool_prompts import EDIT_FILE_DESCRIPTION, UPDATE_FILE_PROMPT_NO_PATH

logger = logging.getLogger(__name__)

branch_description: str = "The name of the branch required to perform corresponding action. e.g. `feature-1`. **IMPORTANT**: if branch not specified, try to determine from the chat history or clarify with user."

GitLabCreateBranch = create_model(
    "GitLabCreateBranchModel",
    branch_name=(str, Field(description="Name of the branch to create")),
    repository=(Optional[str], Field(description="Name of the repository", default=None))
)

GitLabListBranches = create_model(
    "GitLabListBranchesModel",
    repository=(Optional[str], Field(description="Name of the repository", default=None)),
    limit=(Optional[int], Field(description="Maximum number of branches to return. If not provided, all branches will be returned.", default=20, gt=0)),
    branch_wildcard=(Optional[str], Field(description="Wildcard pattern to filter branches by name. If not provided, all branches will be returned.", default=None))
)

GitlabSetActiveBranch = create_model(
    "BranchInput",
    branch=(str, Field(description="The name of the branch, e.g. `my_branch`.")))

GitLabGetIssues = create_model(
    "GitLabGetIssuesModel",
    repository=(Optional[str], Field(description="Name of the repository", default=None))
)

GitLabGetIssue = create_model(
    "GitLabGetIssueModel",
    issue_number=(int, Field(description="Number of the issue to fetch")),
    repository=(Optional[str], Field(description="Name of the repository", default=None))
)

GitLabCreatePullRequest = create_model(
    "GitLabCreatePullRequestModel",
    pr_title=(str, Field(description="Title of the pull request")),
    pr_body=(str, Field(description="Body of the pull request")),
    branch=(str, Field(description=branch_description)),
    repository=(Optional[str], Field(description="Name of the repository", default=None))
)

GitLabCommentOnIssue = create_model(
    "GitLabCommentOnIssueModel",
    comment_query=(str, Field(description="Issue number followed by two newlines and the comment")),
    repository=(Optional[str], Field(description="Name of the repository", default=None))
)

GitLabCreateFile = create_model(
    "GitLabCreateFileModel",
    file_path=(str, Field(description="Path of the file to create")),
    file_contents=(str, Field(description="Contents of the file to create")),
    branch=(str, Field(description=branch_description)),
    repository=(Optional[str], Field(description="Name of the repository", default=None))
)

GitLabReadFile = create_model(
    "GitLabReadFileModel",
    file_path=(str, Field(description="Path of the file to read")),
    branch=(str, Field(description=branch_description)),
    repository=(Optional[str], Field(description="Name of the repository", default=None))
)

GitLabUpdateFile = create_model(
    "GitLabUpdateFile",
    file_path=(str, Field(description="Path of the file to update")),
    update_query=(str, Field(description=UPDATE_FILE_PROMPT_NO_PATH)),
    repository=(Optional[str], Field(description="Name of the repository", default=None)),
    branch=(str, Field(description=branch_description))
)

GitLabDeleteFile = create_model(
    "GitLabDeleteFileModel",
    file_path=(str, Field(description="Path of the file to delete")),
    branch=(str, Field(description=branch_description)),
    repository=(Optional[str], Field(description="Name of the repository", default=None))
)

GitLabGetPRChanges = create_model(
    "GitLabGetPRChanges",
    pr_number=(str, Field(description="Pull request number")),
    repository=(Optional[str], Field(description="Name of the repository", default=None))
)

ListFilesModel = create_model(
    "ListFilesModel",
    path=(str, Field(description="Repository path/package to extract files from.")),
    branch=(Optional[str], Field(description="Repository branch. If None then active branch will be selected.", default=None)),
    repository=(Optional[str], Field(description="Name of the repository", default=None))
)

ListFilesModel = create_model(
    "ListFoldersModel",
    path=(str, Field(description="Repository path/package to extract folders from.")),
    recursive=(Optional[bool], Field(description="Return folders list recursively. Default: True", default=True)),
    branch=(Optional[str], Field(description="Repository branch. If None then active branch will be selected.", default=None)),
    repository=(Optional[str], Field(description="Name of the repository", default=None))
)

GitLabCreatePullRequestChangeCommentInput = create_model(
    "CreatePullRequestChangeCommentInput",
    pr_number=(str, Field(description="Pull request number")),
    file_path=(str, Field(description="File path where the comment should be added")),
    line_number=(int, Field(description="Line number where the comment should be added")),
    comment=(str, Field(description="Comment text to be added")),
    repository=(Optional[str], Field(description="Name of the repository", default=None))
)

AppendFileInput = create_model(
    "AppendFileInput",
    file_path=(str, Field(description="File path where new code should be added")),
    content=(str, Field(description="Code to be appended to existing file")),
    branch=(str, Field(description=branch_description)),
    repository=(Optional[str], Field(description="Name of the repository", default=None))
)

GetCommits = create_model(
    "GetCommits",
    sha=(Optional[str],
         Field(description="The commit SHA to start listing commits from. If not provided, the default branch is used.",
               default=None)),
    path=(Optional[str],
          Field(description="The file path to filter commits by. Only commits affecting this path will be returned.",
                default=None)),
    since=(Optional[str],
           Field(
               description="Only commits after this date will be returned. Use ISO 8601 format (e.g., '2023-01-01T00:00:00Z').",
               default=None)),
    until=(Optional[str],
           Field(
               description="Only commits before this date will be returned. Use ISO 8601 format (e.g., '2023-12-31T23:59:59Z').",
               default=None)),
    author=(Optional[str],
            Field(description="The author of the commits. Can be a username (string)", default=None)),
    repository=(Optional[str], Field(description="Name of the repository", default=None))
)

_misconfigured_alert = "Misconfigured repositories"
_undefined_repo_alert = "Unable to get repository"


# Toolkit API wrapper
class GitLabWorkspaceAPIWrapper(BaseToolApiWrapper):
    url: str
    private_token: SecretStr
    branch: Optional[str] = 'main'
    client: Any = None
    repo_instances: Dict[str, Any] = {}
    _active_branch: Optional[str] = PrivateAttr(default='main')

    # Reuse common file helpers from BaseCodeToolApiWrapper where applicable
    edit_file = BaseCodeToolApiWrapper.edit_file

    class Config:
        arbitrary_types_allowed = True

    @model_validator(mode='before')
    @classmethod
    def validate_toolkit(cls, values):
        """Validate and set up the GitLab client."""
        try:
            import gitlab
            g = gitlab.Gitlab(
                url=values['url'],
                private_token=values['private_token'],
                keep_base_url=True,
            )
            g.auth()
            values['client'] = g
            if values.get('repositories'):
                values['repo_instances'] = {}
                import re
                for repo in re.split(',|;', values.get('repositories')):
                    values['repo_instances'][repo] = g.projects.get(repo)
            values['_active_branch'] = values.get('branch', 'main')
        except Exception as e:
            raise ImportError(f"Failed to connect to GitLab: {e}")
        return values

    def _get_repo_instance(self, repository: str):
        """Get the repository instance, defaulting to the initialized repository if not provided."""
        return self.client.projects.get(repository)

    def _get_repo(self, repository_name: Optional[str] = None) -> Any:
        try:
            # Passed repo as None
            if not repository_name:
                if len(self.repo_instances) == 0:
                    raise ToolException(f"{_misconfigured_alert} >> You haven't configured any repositories. Please, define repository name in chat or add it in tool's configuration.")
                else:
                    return list(self.repo_instances.items())[0][1]
            # Defined repo flow
            if repository_name not in self.repo_instances:
                self.repo_instances[repository_name] = self._get_repo_instance(repository_name)
            return self.repo_instances.get(repository_name)
        except Exception as e:
            if not isinstance(e, ToolException):
                raise ToolException(f"{_undefined_repo_alert} >> {repository_name}: {str(e)}")
            else:
                raise e

    def set_active_branch(self, branch: str) -> str:
        """Set the active branch for the bot."""
        self._active_branch = branch
        return f"Active branch set to {branch}"

    def list_branches_in_repo(self, repository: Optional[str] = None, limit: Optional[int] = 20, branch_wildcard: Optional[str] = None) -> List[str]:
        """
        Lists branches in the repository with optional limit and wildcard filtering.

        Parameters:
            repository (Optional[str]): Name of the repository. If None, uses the active repository.
            limit (Optional[int]): Maximum number of branches to return
            branch_wildcard (Optional[str]): Wildcard pattern to filter branches (e.g., '*dev')

        Returns:
            List[str]: List containing names of branches
        """
        try:
            repo_instance = self._get_repo(repository)
            branches = repo_instance.branches.list(get_all=True)
            
            if branch_wildcard:
                branches = [branch for branch in branches if fnmatch.fnmatch(branch.name, branch_wildcard)]
            
            if limit:
                branches = branches[:limit]
            
            branch_names = [branch.name for branch in branches]
            return branch_names
        except Exception as e:
            return f"Failed to list branches: {str(e)}"

    def create_branch(self, branch_name: str, repository: Optional[str] = None) -> str:
        """Create a new branch in the repository."""
        try:
            repo_instance = self._get_repo(repository)
        except Exception as e:
            return ToolException(e)
        try:
            repo_instance.branches.create(
                {
                    'branch': branch_name,
                    'ref': self._active_branch,
                }
            )
        except Exception as e:
            if "Branch already exists" in str(e):
                self._active_branch = branch_name
                return f"Branch {branch_name} already exists. set it as active"
            return ToolException(f"Unable to create branch due to error:\n{e}")
        self._active_branch = branch_name
        return f"Branch {branch_name} created successfully and set as active"

    def get_issues(self, repository: Optional[str] = None) -> str:
        """Fetches all open issues from the repo."""

        try:
            repo_instance = self._get_repo(repository)
            issues = repo_instance.issues.list(state="opened")
            if issues:
                parsed_issues = [{"title": issue.title, "number": issue.iid} for issue in issues]
                return f"Found {len(parsed_issues)} issues:\n{parsed_issues}"
            else:
                return "No open issues available"
        except Exception as e:
            return ToolException(e)

    def get_issue(self, issue_number: int, repository: Optional[str] = None) -> Dict[str, Any]:
        """Fetches a specific issue and its first 10 comments."""

        try:
            repo_instance = self._get_repo(repository)
            issue = repo_instance.issues.get(issue_number)
            comments = [{"body": comment.body, "user": comment.author["username"]} for comment in issue.notes.list()[:10]]
            return {"title": issue.title, "body": issue.description, "comments": comments}
        except Exception as e:
            return ToolException(e)

    def create_pull_request(self, pr_title: str, pr_body: str, branch: str, repository: Optional[str] = None) -> str:
        """Makes a pull request from the bot's branch to the base branch."""

        try:
            repo_instance = self._get_repo(repository)
        except Exception as e:
            return ToolException(e)

        try:
            pr = repo_instance.mergerequests.create(
                {
                    "source_branch": branch,
                    "target_branch": self.branch,
                    "title": pr_title,
                    "description": pr_body,
                    "labels": ["created-by-agent"],
                }
            )
            return f"Successfully created PR number {pr.iid}"
        except Exception as e:
            return ToolException(f"Unable to make pull request due to error:\n{e}")

    def get_pr_changes(self, pr_number:str, repository: Optional[str] = None):
        """Get pull request changes from the specified pr number and repository."""

        try:
            repo_instance = self._get_repo(repository)
            mr = repo_instance.mergerequests.get(pr_number)
            res = f"""title: {mr.title}\ndescription: {mr.description}\n\n"""

            for change in mr.changes()["changes"]:
                diff_w_position = get_diff_w_position(change=change)
                diff = "\n".join([str(line_num) + ":" + line[1] for line_num, line in diff_w_position.items()])

                res = res + f"""diff --git a/{change["old_path"]} b/{change["new_path"]}\n{diff}\n"""
            return res
        except GitlabGetError as e:
            if e.response_code == 404:
                raise ToolException(f"Merge request number {pr_number} wasn't found: {e}")
        except Exception as e:
            return ToolException(e)

    def comment_on_issue(self, comment_query: str, repository: Optional[str] = None) -> str:
        """Adds a comment to a gitlab issue."""
        try:
            repo_instance = self._get_repo(repository)
            issue_number = int(comment_query.split("\n\n")[0])
            comment = comment_query[len(str(issue_number)) + 2 :]
            try:
                issue = repo_instance.issues.get(issue_number)
                issue.notes.create({"body": comment})
                return f"Commented on issue {issue_number}"
            except Exception as e:
                return f"Unable to make comment due to error:\n{e}"
        except Exception as e:
            return ToolException(e)

    def create_file(self, file_path: str, file_contents: str, branch: str, repository: Optional[str] = None) -> str:
        """Creates a new file on the gitlab repo."""
        try:
            repo_instance = self._get_repo(repository)
            try:
                repo_instance.files.get(file_path, branch)
                return f"File already exists at {file_path}. Use update_file instead"
            except Exception:
                data = {
                    "branch": branch,
                    "commit_message": "Create " + file_path,
                    "file_path": file_path,
                    "content": file_contents,
                }
                repo_instance.files.create(data)
                return "Created file " + file_path
        except Exception as e:
            return ToolException(e)

    def read_file(self, file_path: str, branch: str, repository: Optional[str] = None) -> str:
        """Reads a file from the gitlab repo."""

        try:
            repo_instance = self._get_repo(repository)
            file = repo_instance.files.get(file_path, branch)
            return file.decode().decode("utf-8")
        except Exception as e:
            return ToolException(e)

    def _read_file(self, file_path: str, branch: str, **kwargs) -> str:
        """
        Internal read_file used by BaseCodeToolApiWrapper.edit_file.
        Delegates to the public `read_file` implementation which supports an optional repository argument.
        The repository may be passed via kwargs or provided earlier through `update_file` which sets
        a temporary attribute `_tmp_repository_for_edit`.
        """
        # Repository from temporary context, then None
        repository = getattr(self, "_tmp_repository_for_edit", None)
        try:
            # Public read_file signature: read_file(file_path, branch, repository=None)
            return self.read_file(file_path, branch, repository)
        except Exception as e:
            raise ToolException(f"Can't extract file content (`{file_path}`) due to error:\n{str(e)}")

    def _write_file(self, file_path: str, content: str, branch: str = None, commit_message: str = None) -> str:
        """
        Write content to a file (update only) in the specified GitLab repository.

        This implementation follows the same commit flow as the previous `update_file`:
        it does not attempt to create the file when it is missing — it will always
        create a commit with a single `update` action. If the file does not exist on
        the target branch, the underlying GitLab API will typically return an error.
        """
        try:
            branch = branch if branch else (self._active_branch if self._active_branch else self.branch)
            # pick repository from temporary edit context
            repository = getattr(self, "_tmp_repository_for_edit", None)
            repo_instance = self._get_repo(repository)

            # Always perform an 'update' action commit (do not create file when missing)
            commit = {
                "branch": branch,
                "commit_message": commit_message or f"Update {file_path}",
                "actions": [
                    {
                        "action": "update",
                        "file_path": file_path,
                        "content": content,
                    }
                ],
            }
            repo_instance.commits.create(commit)
            return f"Updated file {file_path}"
        except ToolException:
            raise
        except Exception as e:
            return ToolException(f"Unable to write file due to error: {str(e)}")

    def update_file(self, file_path: str, update_query: str, branch: str, repository: Optional[str] = None) -> str:
        """Updates a file with new content using OLD/NEW markers by delegating to `edit_file`.

        The method sets a temporary repository context so that `edit_file`'s internal
        calls to `_read_file` and `_write_file` operate on the requested repository.
        """
        # Set temporary repository context used by _read_file/_write_file
        self._tmp_repository_for_edit = repository
        try:
            commit_message = f"Update {file_path}"
            return self.edit_file(file_path=file_path, file_query=update_query, branch=branch, commit_message=commit_message)
        except ToolException as e:
            return str(e)
        except Exception as e:
            return ToolException(f"Unable to update file due to error: {str(e)}")
        finally:
            # Clear temporary context
            try:
                delattr(self, "_tmp_repository_for_edit")
            except Exception:
                self._tmp_repository_for_edit = None

    def delete_file(self, file_path: str, branch: str, repository: Optional[str] = None) -> str:
        """Deletes a file from the repo."""
        try:
            repo_instance = self._get_repo(repository)
            repo_instance.files.delete(
                file_path, branch, "Delete " + file_path
            )
            return "Deleted file " + file_path
        except Exception as e:
            return ToolException(f"Unable to delete file due to error: {str(e)}")


    def append_file(self, file_path: str, content: str, branch: str, repository: Optional[str] = None) -> str:
        """
        Appends new content to the end of file.
        Parameters:
            file_path(str): Contains the file path.
                For example:
                /test/hello.txt
            content(str): new content.
            branch(str): branch name (by default: active_branch)
        Returns:
            A success or failure message
        """
        try:
            if not content:
                return "Content to be added is empty. Append file won't be completed"
            file_content = self.read_file(file_path, branch)
            updated_file_content = f"{file_content}\n{content}"
            commit = {
                "branch": branch,
                "commit_message": "Append " + file_path,
                "actions": [
                    {
                        "action": "update",
                        "file_path": file_path,
                        "content": updated_file_content,
                    }
                ],
            }

            self._get_repo(repository).commits.create(commit)
            return "Updated file " + file_path
        except Exception as e:
            return "Unable to update file due to error:\n" + str(e)

    def create_pr_change_comment(self, pr_number: str, file_path: str, line_number: int, comment: str, repository: Optional[str] = None):
        """Create a comment on a pull request change in GitLab."""

        repo = self._get_repo(repository)
        try:
            mr = repo.mergerequests.get(pr_number)
        except GitlabGetError as e:
            if e.response_code == 404:
                raise ToolException(f"Merge request number {pr_number} wasn't found: {e}")
        try:
            position = get_position(file_path=file_path, line_number=line_number, mr=mr)

            mr.discussions.create({"body": comment, "position": position})
            return "Comment added"
        except Exception as e:
            return ToolException(f"An error occurred: {e}")

    def list_files(self, path: str = None, recursive: bool = True, branch: str = None, repository: str = None) -> List[str]:
        """List files by defined path."""

        files = self._get_all_files(path=path, recursive=recursive, branch=branch, repository=repository)
        paths = [file['path'] for file in files if file['type'] == 'blob']
        return f"Files: {paths}"

    def list_folders(self, path: str = None, recursive: bool = True, branch: str = None, repository: str = None) -> List[str]:
        """List folders by defined path."""

        files = self._get_all_files(path=path, recursive=recursive, branch=branch, repository=repository)
        paths = [file['path'] for file in files if file['type'] == 'tree']
        return f"Folders: {paths}"

    def _get_all_files(self, path: str = None, recursive: bool = True, branch: str = None, repository: str = None):
        return self._get_repo(repository).repository_tree(path=path, ref=branch if branch else self._active_branch,
                                                    recursive=recursive, all=True)

    def get_commits(
            self,
            repository: Optional[str] = None,
            sha: Optional[str] = None,
            path: Optional[str] = None,
            since: Optional[str] = None,
            until: Optional[str] = None,
            author: Optional[str] = None,
    ) -> str:
        """
        Retrieves a list of commits from the repository.

        Parameters:
            sha (Optional[str]): The commit SHA to start listing commits from.
            path (Optional[str]): The file path to filter commits by.
            since (Optional[datetime]): Only commits after this date will be returned.
            until (Optional[datetime]): Only commits before this date will be returned.
            author (Optional[str]): The author of the commits.

        Returns:
            str: A list of commit data or an error message.
        """
        try:
            # Prepare the parameters for the API call
            params = {
                "ref_name": sha,
                "path": path,
                "since": datetime.fromisoformat(since) if since else None,
                "until": datetime.fromisoformat(until) if until else None,
                "author": author if isinstance(author, str) else None,
                "all" : True
            }
            # Remove None values from the parameters
            params = {key: value for key, value in params.items() if value is not None}

            # Call the GitHub API to get commits
            commits = self._get_repo(repository).commits.list(**params)

            # Convert the commits to a list of dictionaries for easier processing
            commit_list = [
                {
                    "sha": commit.id,
                    "author": commit.author_name,
                    "createdAt": commit.created_at,
                    "message": commit.message,
                    "url": commit.web_url,
                }
                for commit in commits
            ]

            return commit_list
        except Exception as e:
            return ToolException(f"Unable to retrieve commits due to error:\n{str(e)}")

    def get_available_tools(self):
        """Return a list of available tools."""
        return [
            {
                "name": "create_branch",
                "description": self.create_branch.__doc__ or "Create a new branch in the repository.",
                "args_schema": GitLabCreateBranch,
                "ref": self.create_branch,
            },
            {
                "name": "set_active_branch",
                "description": self.set_active_branch.__doc__ or "Set the active branch for the bot.",
                "args_schema": GitlabSetActiveBranch,
                "ref": self.set_active_branch,
            },
            {
                "name": "list_branches_in_repo",
                "description": self.list_branches_in_repo.__doc__ or "List branches in the repository with optional limit and wildcard filtering.",
                "args_schema": GitLabListBranches,
                "ref": self.list_branches_in_repo,
            },
            {
                "name": "get_issues",
                "description": self.get_issues.__doc__ or "Fetches all open issues from the repository.",
                "args_schema": GitLabGetIssues,
                "ref": self.get_issues,
            },
            {
                "name": "get_issue",
                "description": self.get_issue.__doc__ or "Fetches a specific issue and its first 10 comments.",
                "args_schema": GitLabGetIssue,
                "ref": self.get_issue,
            },
            {
                "name": "create_pull_request",
                "description": self.create_pull_request.__doc__ or "Creates a pull request in the repository.",
                "args_schema": GitLabCreatePullRequest,
                "ref": self.create_pull_request,
            },
            {
                "name": "comment_on_issue",
                "description": self.comment_on_issue.__doc__ or "Adds a comment to a GitLab issue.",
                "args_schema": GitLabCommentOnIssue,
                "ref": self.comment_on_issue,
            },
            {
                "name": "create_file",
                "description": self.create_file.__doc__ or "Creates a new file in the GitLab repository.",
                "args_schema": GitLabCreateFile,
                "ref": self.create_file,
            },
            {
                "name": "read_file",
                "description": self.read_file.__doc__ or "Reads a file from the GitLab repository.",
                "args_schema": GitLabReadFile,
                "ref": self.read_file,
            },
            {
                "name": "update_file",
                "description": EDIT_FILE_DESCRIPTION,
                "args_schema": GitLabUpdateFile,
                "ref": self.update_file,
            },
            {
                "name": "delete_file",
                "description": self.delete_file.__doc__ or "Deletes a file from the GitLab repository.",
                "args_schema": GitLabDeleteFile,
                "ref": self.delete_file,
            },
            {
                "name": "get_pr_changes",
                "description": self.get_pr_changes.__doc__ or "Get pull request changes from the specified PR number and repository.",
                "args_schema": GitLabGetPRChanges,
                "ref": self.get_pr_changes,
            },
            {
                "name": "create_pr_change_comment",
                "description": self.create_pr_change_comment.__doc__ or "Create a comment on a pull request change in GitLab.",
                "args_schema": GitLabCreatePullRequestChangeCommentInput,
                "ref": self.create_pr_change_comment,
            },
            {
                "name": "list_files",
                "description": self.list_files.__doc__ or "List files by defined path.",
                "args_schema": ListFilesModel,
                "ref": self.list_files,
            },
            {
                "name": "list_folders",
                "description": self.list_folders.__doc__ or "List folders by defined path.",
                "args_schema": ListFilesModel,
                "ref": self.list_folders,
            },
            {
                "name": "append_file",
                "description": self.append_file.__doc__ or "Appends new content to the end of a file.",
                "args_schema": AppendFileInput,
                "ref": self.append_file,
            },
            {
                "ref": self.get_commits,
                "name": "get_commits",
                "description": self.get_commits.__doc__ or "Retrieves a list of commits from the repository.",
                "args_schema": GetCommits,
            }
        ]