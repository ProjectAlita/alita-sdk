# api_wrapper.py
from typing import Any, Dict, List, Optional

from alita_sdk.tools.elitea_base import BaseCodeToolApiWrapper
from pydantic import create_model, Field, model_validator, SecretStr, PrivateAttr

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
    file_query=(str, Field(description="The file query string")),
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

CreateBranchModel = create_model(
    "CreateBranchModel",
    branch_name=(str, Field(description="The name of the branch, e.g. `my_branch`.")),
)
ListBranchesInRepoModel = create_model(
    "ListBranchesInRepoModel",
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
    file_path=(str, Field(description="File path of the changed file")),
    line_number=(int, Field(description="Line number from the diff for a changed file")),
    comment=(str, Field(description="Comment content")),
)
GetCommitsModel = create_model(
    "GetCommitsModel",
    sha=(Optional[str], Field(description="Commit SHA", default=None)),
    path=(Optional[str], Field(description="File path", default=None)),
    since=(Optional[str], Field(description="Start date", default=None)),
    until=(Optional[str], Field(description="End date", default=None)),
    author=(Optional[str], Field(description="Author name", default=None)),
)

class GitLabAPIWrapper(BaseCodeToolApiWrapper):
    url: str
    repository: str
    private_token: SecretStr
    branch: Optional[str] = 'main'
    _git: Any = PrivateAttr()
    _repo_instance: Any = PrivateAttr()
    _active_branch: Any = PrivateAttr()

    llm: Optional[Any] = None
    # Alita instance
    alita: Optional[Any] = None

    # Vector store configuration
    connection_string: Optional[SecretStr] = None
    collection_name: Optional[str] = None
    doctype: Optional[str] = 'code'
    embedding_model: Optional[str] = "HuggingFaceEmbeddings"
    embedding_model_params: Optional[Dict[str, Any]] = {"model_name": "sentence-transformers/all-MiniLM-L6-v2"}
    vectorstore_type: Optional[str] = "PGVector"

    @model_validator(mode='before')
    @classmethod
    def validate_toolkit(cls, values: Dict) -> Dict:
        try:
            import gitlab
        except ImportError:
            raise ImportError(
                "python-gitlab is not installed. "
                "Please install it with `pip install python-gitlab`"
            )

        g = gitlab.Gitlab(
            url=values['url'],
            private_token=values['private_token'],
            keep_base_url=True,
        )

        g.auth()
        cls._repo_instance = g.projects.get(values.get('repository'))
        cls._git = g
        cls._active_branch = values.get('branch')
        return values

    def set_active_branch(self, branch_name: str) -> str:
        self._active_branch = branch_name
        self._repo_instance.default_branch = branch_name
        return f"Active branch set to {branch_name}"

    def list_branches_in_repo(self) -> List[str]:
        branches = self._repo_instance.branches.list()
        return [branch.name for branch in branches]

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
        return self._repo_instance.repository_tree(path=path, ref=branch, recursive=recursive, all=True)

    # overrided for indexer
    def _get_files(self, path: str = None, recursive: bool = True, branch: str = None):
        gitlab_files = self._get_all_files(path, recursive, branch)
        return [file['path'] for file in gitlab_files if file['type'] == 'blob']

    def _file_commit_hash(self, file_path: str, branch: str):
        """
        Get the commit hash of a file in a specific branch.
        """
        try:
            file = self._repo_instance.files.get(file_path, branch)
            return file.commit_id
        except Exception as e:
            return f"Unable to get commit hash for {file_path} due to error:\n{e}"

    def _read_file(self, file_path: str, branch: str):
        return self.read_file(file_path, branch)

    def create_branch(self, branch_name: str) -> str:
        try:
            self._repo_instance.branches.create(
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
        issues = self._repo_instance.issues.list(state="opened")
        if len(issues) > 0:
            parsed_issues = self.parse_issues(issues)
            parsed_issues_str = (
                    "Found " + str(len(parsed_issues)) + " issues:\n" + str(parsed_issues)
            )
            return parsed_issues_str
        else:
            return "No open issues available"

    def get_issue(self, issue_number: int) -> Dict[str, Any]:
        issue = self._repo_instance.issues.get(issue_number)
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
                pr = self._repo_instance.mergerequests.create(
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
            issue = self._repo_instance.issues.get(issue_number)
            issue.notes.create({"body": comment})
            return "Commented on issue " + str(issue_number)
        except Exception as e:
            return "Unable to make comment due to error:\n" + str(e)

    def create_file(self, file_path: str, file_contents: str, branch: str) -> str:
        try:
            self.set_active_branch(branch)
            self._repo_instance.files.get(file_path, branch)
            return f"File already exists at {file_path}. Use update_file instead"
        except Exception:
            data = {
                "branch": branch,
                "commit_message": "Create " + file_path,
                "file_path": file_path,
                "content": file_contents,
            }
            self._repo_instance.files.create(data)

            return "Created file " + file_path

    def read_file(self, file_path: str, branch: str) -> str:
        self.set_active_branch(branch)
        file = self._repo_instance.files.get(file_path, branch)
        return file.decode().decode("utf-8")

    def update_file(self, file_query: str, branch: str) -> str:
        if branch == self.branch:
            return (
                "You're attempting to commit to the directly"
                f"to the {self.branch} branch, which is protected. "
                "Please create a new branch and try again."
            )
        try:
            file_path: str = file_query.split("\n")[0]
            self.set_active_branch(branch)
            file_content = self.read_file(file_path, branch)
            updated_file_content = file_content
            for old, new in self.extract_old_new_pairs(file_query):
                if not old.strip():
                    continue
                updated_file_content = updated_file_content.replace(old, new)

            if file_content == updated_file_content:
                return (
                    "File content was not updated because old content was not found or empty."
                    "It may be helpful to use the read_file action to get "
                    "the current file contents."
                )

            commit = {
                "branch": branch,
                "commit_message": "Create " + file_path,
                "actions": [
                    {
                        "action": "update",
                        "file_path": file_path,
                        "content": updated_file_content,
                    }
                ],
            }

            self._repo_instance.commits.create(commit)
            return "Updated file " + file_path
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

            self._repo_instance.commits.create(commit)
            return "Updated file " + file_path
        except Exception as e:
            return "Unable to update file due to error:\n" + str(e)

    def delete_file(self, file_path: str, branch: str, commit_message: str = None) -> str:
        try:
            self.set_active_branch(branch)
            if not commit_message:
                commit_message = f"Delete {file_path}"
            self._repo_instance.files.delete(file_path, branch, commit_message)
            return f"Deleted file {file_path}"
        except Exception as e:
            return f"Unable to delete file due to error:\n{e}"

    def get_pr_changes(self, pr_number: int) -> str:
        mr = self._repo_instance.mergerequests.get(pr_number)
        res = f"title: {mr.title}\ndescription: {mr.description}\n\n"
        for change in mr.changes()["changes"]:
            res += f"diff --git a/{change['old_path']} b/{change['new_path']}\n{change['diff']}\n"
        return res

    def create_pr_change_comment(self, pr_number: int, file_path: str, line_number: int, comment: str) -> str:
        mr = self._repo_instance.mergerequests.get(pr_number)
        position = {"position_type": "text", "new_path": file_path, "new_line": line_number}
        mr.discussions.create({"body": comment, "position": position})
        return "Comment added"

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
        commits = self._repo_instance.commits.list(**params)
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

    def get_available_tools(self):
        return [
            {
                "name": "create_branch",
                "ref": self.create_branch,
                "description": self.create_branch.__doc__,
                "args_schema": CreateBranchModel,
            },
            {
                "name": "list_branches_in_repo",
                "ref": self.list_branches_in_repo,
                "description": self.list_branches_in_repo.__doc__,
                "args_schema": ListBranchesInRepoModel,
            },
            {
                "name": "list_files",
                "ref": self.list_files,
                "description": self.list_files.__doc__,
                "args_schema": ListFilesModel,
            },
            {
                "name": "list_folders",
                "ref": self.list_folders,
                "description": self.list_folders.__doc__,
                "args_schema": ListFoldersModel,
            },
            {
                "name": "get_issues",
                "ref": self.get_issues,
                "description": self.get_issues.__doc__,
                "args_schema": GetIssuesModel,
            },
            {
                "name": "get_issue",
                "ref": self.get_issue,
                "description": self.get_issue.__doc__,
                "args_schema": GetIssueModel,
            },
            {
                "name": "create_pull_request",
                "ref": self.create_pull_request,
                "description": self.create_pull_request.__doc__,
                "args_schema": CreatePullRequestModel,
            },
            {
                "name": "comment_on_issue",
                "ref": self.comment_on_issue,
                "description": self.comment_on_issue.__doc__,
                "args_schema": CommentOnIssueModel,
            },
            {
                "name": "create_file",
                "ref": self.create_file,
                "description": self.create_file.__doc__,
                "args_schema": CreateFileModel,
            },
            {
                "name": "read_file",
                "ref": self.read_file,
                "description": self.read_file.__doc__,
                "args_schema": ReadFileModel,
            },
            {
                "name": "update_file",
                "ref": self.update_file,
                "description": self.update_file.__doc__,
                "args_schema": UpdateFileModel,
            },
            {
                "name": "append_file",
                "ref": self.append_file,
                "description": self.append_file.__doc__,
                "args_schema": AppendFileModel,
            },
            {
                "name": "delete_file",
                "ref": self.delete_file,
                "description": self.delete_file.__doc__,
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
                "description": "Create a comment on a pull request change.",
                "args_schema": CreatePRChangeCommentModel,
            },
            {
                "name": "get_commits",
                "ref": self.get_commits,
                "description": "Retrieve a list of commits from the repository.",
                "args_schema": GetCommitsModel,
            },
        ] + self._get_vector_search_tools()