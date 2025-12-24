# api_wrapper.py
import fnmatch
from typing import Any, Dict, List, Optional

from gitlab import GitlabGetError
from langchain_core.tools import ToolException
from pydantic import create_model, Field, model_validator, SecretStr, PrivateAttr

from ..code_indexer_toolkit import CodeIndexerToolkit
from ..utils.available_tools_decorator import extend_with_parent_available_tools
from ..elitea_base import extend_with_file_operations, BaseCodeToolApiWrapper
from ..utils.content_parser import parse_file_content
from .utils import get_position

AppendFileModel = create_model(
    "AppendFileModel",
    file_path=(str, Field(description="The path of the file")),
    content=(str, Field(description="The content to append to the file")),
    branch=(str, Field(description="The branch to append the file in")),
)
DeleteFileModel = create_model(
    "DeleteFileModel",
    file_path=(str, Field(description="The path of the file")),
    branch=(str, Field(description="The branch to delete the file from")),
    commit_message=(str, Field(default=None, description="Commit message for deleting the file. Optional.")),
)
CreateFileModel = create_model(
    "CreateFileModel",
    file_path=(str, Field(description="The path of the file")),
    file_contents=(str, Field(description="The contents of the file")),
    branch=(str, Field(description="The branch to create the file in")),
)
ReadFileModel = create_model(
    "ReadFileModel",
    file_path=(str, Field(description="The path of the file")),
    branch=(str, Field(description="The branch to read the file from")),
)
UpdateFileModel = create_model(
    "UpdateFileModel",
    file_query=(str, Field(description="The file query string containing file path on first line, followed by OLD/NEW markers. Format: file_path\\nOLD <<<< old content >>>> OLD\\nNEW <<<< new content >>>> NEW")),
    branch=(str, Field(description="The branch to update the file in")),
)
CommentOnIssueModel = create_model(
    "CommentOnIssueModel",
    comment_query=(str, Field(description="The comment query string")),
)
GetIssueModel = create_model(
    "GetIssueModel",
    issue_number=(int, Field(description="The number of the issue")),
)
CreatePullRequestModel = create_model(
    "CreatePullRequestModel",
    pr_title=(str, Field(description="The title of the pull request")),
    pr_body=(str, Field(description="The body of the pull request")),
    branch=(str, Field(description="The branch to create the pull request from")),
)
CommentOnPRModel = create_model(
    "CommentOnPRModel",
    pr_number=(int, Field(description="The number of the pull request/merge request")),
    comment=(str, Field(description="The comment text to add")),
)

CreateBranchModel = create_model(
    "CreateBranchModel",
    branch_name=(str, Field(description="The name of the branch, e.g. `my_branch`.")),
)
ListBranchesInRepoModel = create_model(
    "ListBranchesInRepoModel",
    limit=(Optional[int], Field(default=20, description="Maximum number of branches to return. If not provided, all branches will be returned.")),
    branch_wildcard=(Optional[str], Field(default=None, description="Wildcard pattern to filter branches by name. If not provided, all branches will be returned."))

)

ListFilesModel = create_model(
    "ListFilesModel",
    path=(Optional[str], Field(description="The path to list files from")),
    recursive=(bool, Field(description="Whether to list files recursively", default=True)),
    branch=(Optional[str], Field(description="The branch to list files from")),
)
ListFoldersModel = create_model(
    "ListFoldersModel",
    path=(Optional[str], Field(description="The path to list folders from")),
    recursive=(bool, Field(description="Whether to list folders recursively", default=True)),
    branch=(Optional[str], Field(description="The branch to list folders from")),
)
GetIssuesModel = create_model(
    "GetIssuesModel",
)
SetActiveBranchModel = create_model(
    "SetActiveBranchModel",
    branch_name=(str, Field(description="The name of the branch, e.g. `my_branch`.")),
)
GetPRChangesModel = create_model(
    "GetPRChangesModel",
    pr_number=(int, Field(description="GitLab Merge Request (Pull Request) number")),
)
CreatePRChangeCommentModel = create_model(
    "CreatePRChangeCommentModel",
    pr_number=(int, Field(description="GitLab Merge Request (Pull Request) number")),
    file_path=(str, Field(description="File path of the changed file as shown in the diff")),
    line_number=(int, Field(description="Line index (0-based) from the diff output. Use get_pr_changes first to see the diff and identify the correct line index to comment on.")),
    comment=(str, Field(description="Comment content to add to the specific line")),
)
GetCommitsModel = create_model(
    "GetCommitsModel",
    sha=(Optional[str], Field(description="Commit SHA", default=None)),
    path=(Optional[str], Field(description="File path", default=None)),
    since=(Optional[str], Field(description="Start date", default=None)),
    until=(Optional[str], Field(description="End date", default=None)),
    author=(Optional[str], Field(description="Author name", default=None)),
)

class GitLabAPIWrapper(CodeIndexerToolkit):
    url: str
    repository: str
    private_token: SecretStr
    branch: Optional[str] = 'main'
    _git: Any = PrivateAttr()
    _active_branch: Any = PrivateAttr()
    
    # Import file operation methods from BaseCodeToolApiWrapper
    read_file_chunk = BaseCodeToolApiWrapper.read_file_chunk
    read_multiple_files = BaseCodeToolApiWrapper.read_multiple_files
    search_file = BaseCodeToolApiWrapper.search_file
    edit_file = BaseCodeToolApiWrapper.edit_file

    @staticmethod
    def _sanitize_url(url: str) -> str:
        """Remove trailing slash from URL if present."""
        return url.rstrip('/') if url else url

    @model_validator(mode='before')
    @classmethod
    def validate_toolkit_before(cls, values: Dict) -> Dict:
        return super().validate_toolkit(values)

    @model_validator(mode='after')
    def validate_toolkit(self):
        try:
           import gitlab
        except ImportError:
            raise ImportError(
                "python-gitlab is not installed. "
                "Please install it with `pip install python-gitlab`"
            )
        self.repository = self._sanitize_url(self.repository)
        g = gitlab.Gitlab(
            url=self._sanitize_url(self.url),
            private_token=self.private_token.get_secret_value(),
            keep_base_url=True,
        )

        g.auth()
        self._git = g
        self._active_branch = self.branch
        return self

    @property
    def repo_instance(self):
        if not hasattr(self, "_repo_instance") or self._repo_instance is None:
            try:
                if self._git and self.repository:
                    self._repo_instance = self._git.projects.get(self.repository)
                else:
                    self._repo_instance = None
            except Exception as e:
                # Only raise when accessed, not during initialization
                raise ToolException(e)
        return self._repo_instance

    def set_active_branch(self, branch_name: str) -> str:
        self._active_branch = branch_name
        self.repo_instance.default_branch = branch_name
        return f"Active branch set to {branch_name}"

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
            branches = self.repo_instance.branches.list(get_all=True)
            
            if branch_wildcard:
                branches = [branch for branch in branches if fnmatch.fnmatch(branch.name, branch_wildcard)]
            
            if limit is not None:
                branches = branches[:limit]
            
            branch_names = [branch.name for branch in branches]
            return branch_names
        except Exception as e:
            return f"Failed to list branches: {str(e)}"

    def list_files(self, path: str = None, recursive: bool = True, branch: str = None) -> List[str]:
        branch = branch if branch else self._active_branch
        files = self._get_all_files(path, recursive, branch)
        paths = [file['path'] for file in files if file['type'] == 'blob']
        return paths

    def list_folders(self, path: str = None, recursive: bool = True, branch: str = None) -> List[str]:
        branch = branch if branch else self._active_branch
        files = self._get_all_files(path, recursive, branch)
        paths = [file['path'] for file in files if file['type'] == 'tree']
        return paths

    def _get_all_files(self, path: str = None, recursive: bool = True, branch: str = None):
        branch = branch if branch else self._active_branch
        return self.repo_instance.repository_tree(path=path, ref=branch, recursive=recursive, all=True)

    # overrided for indexer
    def _get_files(self, path: str = None, recursive: bool = True, branch: str = None):
        gitlab_files = self._get_all_files(path, recursive, branch)
        return [file['path'] for file in gitlab_files if file['type'] == 'blob']

    def _file_commit_hash(self, file_path: str, branch: str):
        """
        Get the commit hash of a file in a specific branch.
        """
        try:
            file = self.repo_instance.files.get(file_path, branch)
            return file.commit_id
        except Exception as e:
            return f"Unable to get commit hash for {file_path} due to error:\n{e}"

    def _read_file(self, file_path: str, branch: str, **kwargs):
        """
        Read a file from specified branch with optional partial read support.
        
        Parameters:
            file_path: the file path
            branch: the branch to read the file from
            **kwargs: Additional parameters (offset, limit, head, tail) - currently ignored,
                     partial read handled client-side by base class methods
        
        Returns:
            File content as string
        """
        # Default to active branch if branch is None, consistent with other methods
        branch = branch if branch else self._active_branch
        return self.read_file(file_path, branch)

    def create_branch(self, branch_name: str) -> str:
        try:
            self.repo_instance.branches.create(
                {
                    'branch': branch_name,
                    'ref': self._active_branch,
                }
            )
        except Exception as e:
            if "Branch already exists" in str(e):
                self._active_branch = branch_name
                return f"Branch {branch_name} already exists. set it as active"
            return f"Unable to create branch due to error:\n{e}"
        self._active_branch = branch_name
        return f"Branch {branch_name} created successfully and set as active"

    def parse_issues(self, issues: List[Any]) -> List[dict]:
        parsed = []
        for issue in issues:
            title = issue.title
            number = issue.iid
            parsed.append({"title": title, "number": number})
        return parsed

    def get_issues(self) -> str:
        issues = self.repo_instance.issues.list(state="opened")
        if len(issues) > 0:
            parsed_issues = self.parse_issues(issues)
            parsed_issues_str = (
                    "Found " + str(len(parsed_issues)) + " issues:\n" + str(parsed_issues)
            )
            return parsed_issues_str
        else:
            return "No open issues available"

    def get_issue(self, issue_number: int) -> Dict[str, Any]:
        issue = self.repo_instance.issues.get(issue_number)
        page = 0
        comments: List[dict] = []
        while len(comments) <= 10:
            comments_page = issue.notes.list(page=page)
            if len(comments_page) == 0:
                break
            for comment in comments_page:
                comment = issue.notes.get(comment.id)
                comments.append(
                    {"body": comment.body, "user": comment.author["username"]}
                )
            page += 1

        return {
            "title": issue.title,
            "body": issue.description,
            "comments": str(comments),
        }

    def create_pull_request(self, pr_title: str, pr_body: str, branch: str) -> str:
        if self.branch == branch:
            return f"""Cannot make a pull request because 
            commits are already in the {self.branch} branch"""
        else:
            try:
                pr = self.repo_instance.mergerequests.create(
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
                return "Unable to make pull request due to error:\n" + str(e)

    def comment_on_issue(self, comment_query: str) -> str:
        issue_number = int(comment_query.split("\n\n")[0])
        comment = comment_query[len(str(issue_number)) + 2 :]
        try:
            issue = self.repo_instance.issues.get(issue_number)
            issue.notes.create({"body": comment})
            return "Commented on issue " + str(issue_number)
        except Exception as e:
            return "Unable to make comment due to error:\n" + str(e)

    def comment_on_pr(self, pr_number: int, comment: str) -> str:
        """
        Add a comment to a pull request (merge request) in GitLab.

        This method adds a general comment to the entire merge request,
        not tied to specific code lines or file changes.

        Parameters:
            pr_number: GitLab Merge Request (Pull Request) number
            comment: Comment text to add

        Returns:
            Success message or error description
        """
        try:
            mr = self.repo_instance.mergerequests.get(pr_number)
            mr.notes.create({"body": comment})
            return "Commented on merge request " + str(pr_number)
        except Exception as e:
            return "Unable to make comment due to error:\n" + str(e)

    def create_file(self, file_path: str, file_contents: str, branch: str) -> str:
        # Default to active branch if branch is None
        branch = branch if branch else self._active_branch
        try:
            self.set_active_branch(branch)
            self.repo_instance.files.get(file_path, branch)
            return f"File already exists at {file_path}. Use update_file instead"
        except Exception:
            data = {
                "branch": branch,
                "commit_message": "Create " + file_path,
                "file_path": file_path,
                "content": file_contents,
            }
            self.repo_instance.files.create(data)

            return "Created file " + file_path

    def read_file(self, file_path: str, branch: str) -> str:
        # Default to active branch if branch is None
        branch = branch if branch else self._active_branch
        self.set_active_branch(branch)
        file = self.repo_instance.files.get(file_path, branch)
        return parse_file_content(file_name=file_path,
                                  file_content=file.decode(),
                                  llm=self.llm)
    
    def _write_file(
        self,
        file_path: str,
        content: str,
        branch: str = None,
        commit_message: str = None
    ) -> str:
        """
        Write content to a file (create or update).
        
        Parameters:
            file_path: Path to the file
            content: New file content
            branch: Branch name (uses active branch if None)
            commit_message: Commit message
            
        Returns:
            Success message
        """
        try:
            branch = branch or self._active_branch
            
            if branch == self.branch:
                raise ToolException(
                    f"Cannot commit directly to the {self.branch} branch. "
                    "Please create a new branch and try again."
                )
            
            self.set_active_branch(branch)
            
            # Check if file exists
            try:
                self.repo_instance.files.get(file_path, branch)
                # File exists, update it
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
                self.repo_instance.commits.create(commit)
                return f"Updated file {file_path}"
            except:
                # File doesn't exist, create it
                data = {
                    "branch": branch,
                    "commit_message": commit_message or f"Create {file_path}",
                    "file_path": file_path,
                    "content": content,
                }
                self.repo_instance.files.create(data)
                return f"Created file {file_path}"
        except Exception as e:
            raise ToolException(f"Unable to write file {file_path}: {str(e)}")

    def update_file(self, file_query: str, branch: str) -> str:
        """
        Update file using edit_file functionality.

        This method now delegates to edit_file which uses OLD/NEW markers.
        For backwards compatibility, it extracts the file_path from the query.

        Expected format:
            file_path
            OLD <<<<
            old content
            >>>> OLD
            NEW <<<<
            new content
            >>>> NEW

        Args:
            file_query: File path on first line, followed by OLD/NEW markers
            branch: Branch to update the file in

        Returns:
            Success or error message
        """
        if branch == self.branch:
            return (
                "You're attempting to commit directly "
                f"to the {self.branch} branch, which is protected. "
                "Please create a new branch and try again."
            )
        try:
            # Extract file path from first line
            lines = file_query.split("\n", 1)
            if len(lines) < 2:
                return (
                    "Invalid file_query format. Expected:\n"
                    "file_path\n"
                    "OLD <<<< old content >>>> OLD\n"
                    "NEW <<<< new content >>>> NEW"
                )

            file_path = lines[0].strip()
            edit_content = lines[1] if len(lines) > 1 else ""

            # Delegate to edit_file method with appropriate commit message
            commit_message = f"Update {file_path}"
            return self.edit_file(file_path, edit_content, branch, commit_message)

        except Exception as e:
            return "Unable to update file due to error:\n" + str(e)

    def append_file(self, file_path: str, content: str, branch: str) -> str:
        if branch == self.branch:
            return (
                "You're attempting to commit to the directly"
                f"to the {self.branch} branch, which is protected. "
                "Please create a new branch and try again."
            )
        try:
            if not content:
                return "Content to be added is empty. Append file won't be completed"
            self.set_active_branch(branch)
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

            self.repo_instance.commits.create(commit)
            return "Updated file " + file_path
        except Exception as e:
            return "Unable to update file due to error:\n" + str(e)

    def delete_file(self, file_path: str, branch: str, commit_message: str = None) -> str:
        try:
            self.set_active_branch(branch)
            if not commit_message:
                commit_message = f"Delete {file_path}"
            self.repo_instance.files.delete(file_path, branch, commit_message)
            return f"Deleted file {file_path}"
        except Exception as e:
            return f"Unable to delete file due to error:\n{e}"

    def get_pr_changes(self, pr_number: int) -> str:
        mr = self.repo_instance.mergerequests.get(pr_number)
        res = f"title: {mr.title}\ndescription: {mr.description}\n\n"
        for change in mr.changes()["changes"]:
            res += f"diff --git a/{change['old_path']} b/{change['new_path']}\n{change['diff']}\n"
        return res

    def create_pr_change_comment(self, pr_number: int, file_path: str, line_number: int, comment: str) -> str:
        """
        Create a comment on a specific line in a pull request (merge request) change in GitLab.

        This method adds an inline comment to a specific line in the diff of a merge request.
        The line_number parameter refers to the line index in the diff output (0-based),
        not the line number in the original file.

        **Important**: Use get_pr_changes first to see the diff and identify the correct
        line index for commenting.

        Parameters:
            pr_number: GitLab Merge Request number
            file_path: Path to the file being commented on (as shown in the diff)
            line_number: Line index from the diff (0-based index)
            comment: Comment text to add

        Returns:
            Success message or error description
        """
        try:
            mr = self.repo_instance.mergerequests.get(pr_number)
        except GitlabGetError as e:
            if e.response_code == 404:
                raise ToolException(f"Merge request number {pr_number} wasn't found: {e}")
            raise ToolException(f"Error retrieving merge request {pr_number}: {e}")

        try:
            # Calculate proper position with SHA references and line mappings
            position = get_position(file_path=file_path, line_number=line_number, mr=mr)

            # Create discussion with the comment
            mr.discussions.create({"body": comment, "position": position})
            return f"Comment added successfully to line {line_number} in {file_path} on MR #{pr_number}"
        except Exception as e:
            raise ToolException(f"Failed to create comment on MR #{pr_number}: {e}")

    def get_commits(self, sha: Optional[str] = None, path: Optional[str] = None, since: Optional[str] = None, until: Optional[str] = None, author: Optional[str] = None):
        params = {}
        if sha:
            params["ref_name"] = sha
        if path:
            params["path"] = path
        if since:
            params["since"] = since
        if until:
            params["until"] = until
        if author:
            params["author"] = author
        commits = self.repo_instance.commits.list(**params)
        return [
            {
                "sha": commit.id,
                "author": commit.author_name,
                "createdAt": commit.created_at,
                "message": commit.message,
                "url": commit.web_url,
            }
            for commit in commits
        ]

    @extend_with_parent_available_tools
    @extend_with_file_operations
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
                "name": "list_folders",
                "ref": self.list_folders,
                "description": self.list_folders.__doc__ or "List folders in the repository with optional path, recursive search, and branch.",
                "args_schema": ListFoldersModel,
            },
            {
                "name": "get_issues",
                "ref": self.get_issues,
                "description": self.get_issues.__doc__ or "Get all open issues in the repository.",
                "args_schema": GetIssuesModel,
            },
            {
                "name": "get_issue",
                "ref": self.get_issue,
                "description": self.get_issue.__doc__ or "Get details of a specific issue by its number.",
                "args_schema": GetIssueModel,
            },
            {
                "name": "create_pull_request",
                "ref": self.create_pull_request,
                "description": self.create_pull_request.__doc__ or "Create a pull request (merge request) in the repository.",
                "args_schema": CreatePullRequestModel,
            },
            {
                "name": "comment_on_issue",
                "ref": self.comment_on_issue,
                "description": self.comment_on_issue.__doc__ or "Comment on an issue in the repository.",
                "args_schema": CommentOnIssueModel,
            },
            {
                "name": "comment_on_pr",
                "ref": self.comment_on_pr,
                "description": self.comment_on_pr.__doc__ or "Comment on a pull request (merge request) in the repository.",
                "args_schema": CommentOnPRModel,
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
                "name": "append_file",
                "ref": self.append_file,
                "description": self.append_file.__doc__ or "Append content to a file in the repository.",
                "args_schema": AppendFileModel,
            },
            {
                "name": "delete_file",
                "ref": self.delete_file,
                "description": self.delete_file.__doc__ or "Delete a file from the repository.",
                "args_schema": DeleteFileModel,
            },
            {
                "name": "set_active_branch",
                "ref": self.set_active_branch,
                "description": "Set the active branch in the repository.",
                "args_schema": SetActiveBranchModel,
            },
            {
                "name": "get_pr_changes",
                "ref": self.get_pr_changes,
                "description": "Get all changes from a pull request in git diff format.",
                "args_schema": GetPRChangesModel,
            },
            {
                "name": "create_pr_change_comment",
                "ref": self.create_pr_change_comment,
                "description": self.create_pr_change_comment.__doc__ or "Create an inline comment on a specific line in a pull request change. Use get_pr_changes first to see the diff and identify the line index for commenting. The line_number is a 0-based index from the diff output, not the file line number.",
                "args_schema": CreatePRChangeCommentModel,
            },
            {
                "name": "get_commits",
                "ref": self.get_commits,
                "description": "Retrieve a list of commits from the repository.",
                "args_schema": GetCommitsModel,
            }
        ]