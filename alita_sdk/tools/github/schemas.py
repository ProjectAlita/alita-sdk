from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, SecretStr, create_model

# Base schemas for GitHub API wrapper
class GitHubAuthConfig(BaseModel):
    github_access_token: Optional[SecretStr] = None
    github_username: Optional[str] = None
    github_password: Optional[SecretStr] = None
    github_app_id: Optional[str] = None
    github_app_private_key: Optional[SecretStr] = None
    github_base_url: Optional[str] = None

class GitHubRepoConfig(BaseModel):
    github_repository: Optional[str] = None
    active_branch: Optional[str] = None
    github_base_branch: Optional[str] = None

# Schemas for API methods
NoInput = create_model("NoInput")

BranchName = create_model(
    "BranchName",
    branch_name=(str, Field(description="The name of the branch, e.g. `main`"))
)

CreateBranchName = create_model(
    "CreateBranchName",
    proposed_branch_name=(str, Field(description="The name of the new branch to create, e.g. `feature-branch`"))
)

DirectoryPath = create_model(
    "DirectoryPath",
    directory_path=(str, Field(description="The path of the directory, e.g. `src/my_dir`"))
)

ReadFile = create_model(
    "ReadFile",
    file_path=(str, Field(description="The path to the file to read, e.g. `src/main.py`")),
    branch=(Optional[str], Field(description="The branch to read the file from, e.g. `main`", default=None)),
    repo_name=(Optional[str], Field(default=None, description="Name of the repository (e.g., 'owner/repo'). If None, uses the default repository."))
)

UpdateFile = create_model(
    "UpdateFile",
    file_query=(str, Field(description="File path and content to update with OLD and NEW markers")),
    repo_name=(Optional[str], Field(default=None, description="Name of the repository (e.g., 'owner/repo'). If None, uses the default repository.")),
    commit_message=(Optional[str], Field(default=None, description="Commit message for the update operation")),
)

CreateFile = create_model(
    "CreateFile",
    file_path=(str, Field(description="The path of the file to create, e.g. `src/new_file.py`")),
    file_contents=(str, Field(description="The contents to write to the file")),
    repo_name=(Optional[str], Field(default=None, description="Name of the repository (e.g., 'owner/repo'). If None, uses the default repository."))
)

DeleteFile = create_model(
    "DeleteFile",
    file_path=(str, Field(description="The path of the file to delete, e.g. `src/old_file.py`")),
    repo_name=(Optional[str], Field(default=None, description="Name of the repository (e.g., 'owner/repo'). If None, uses the default repository."))
)

GetIssue = create_model(
    "GetIssue",
    issue_number=(int, Field(description="The issue number as a int, e.g. `42`")),
    repo_name=(Optional[str], Field(default=None, description="Name of the repository (e.g., 'owner/repo'). If None, uses the default repository."))
)

GetPR = create_model(
    "GetPR",
    pr_number=(int, Field(description="The PR number as a int, e.g. `42`")),
    repo_name=(Optional[str], Field(default=None, description="Name of the repository (e.g., 'owner/repo'). If None, uses the default repository."))
)

CreatePR = create_model(
    "CreatePR",
    title=(str, Field(description="Title of the pull request")),
    body=(str, Field(description="Body of the pull request")),
    head=(Optional[str], Field(description="The branch containing the changes (defaults to active_branch)")),
    base=(Optional[str], Field(description="The target branch (defaults to github_base_branch)")),
    repo_name=(Optional[str], Field(default=None, description="Name of the repository (e.g., 'owner/repo'). If None, uses the default repository."))
)

CommentOnIssue = create_model(
    "CommentOnIssue",
    issue_number=(str, Field(description="The issue or PR number as a string, e.g. `42`")),
    comment=(str, Field(description="The comment text to add to the issue or PR")),
    repo_name=(Optional[str], Field(default=None, description="Name of the repository (e.g., 'owner/repo'). If None, uses the default repository."))
)

SearchIssues = create_model(
    "SearchIssues",
    search_query=(str, Field(description="Keywords or query for searching issues and PRs in Github")),
    repo_name=(Optional[str], Field(description="Name of the repository to search issues in", default=None)),
    max_count=(Optional[int], Field(description="Maximum number of issues to return", default=30))
)

CreateIssue = create_model(
    "CreateIssue",
    title=(str, Field(description="The title of the issue")),
    body=(Optional[str], Field(description="The detailed description of the issue", default=None)),
    repo_name=(Optional[str], Field(description="Name of the repository to create the issue in", default=None)),
    labels=(Optional[List[str]], Field(description="An optional list of labels to attach to the issue", default=None)),
    assignees=(Optional[List[str]], Field(description="An optional list of GitHub usernames to assign the issue to", default=None))
)

UpdateIssue = create_model(
    "UpdateIssue",
    issue_id=(int, Field(description="ID of the issue to update")),
    title=(Optional[str], Field(description="New title of the issue", default=None)),
    body=(Optional[str], Field(description="New detailed description of the issue", default=None)),
    labels=(Optional[List[str]], Field(description="New list of labels to apply to the issue", default=None)),
    assignees=(Optional[List[str]], Field(description="New list of GitHub usernames to assign to the issue", default=None)),
    state=(Optional[str], Field(description="New state of the issue ('open' or 'closed')", default=None)),
    repo_name=(Optional[str], Field(description="Name of the repository where the issue exists", default=None))
)

LoaderSchema = create_model(
    "LoaderSchema",
    branch=(Optional[str], Field(description="The branch to set as active. If None, the current active branch is used.", default=None)),
    whitelist=(Optional[List[str]], Field(description="A list of file extensions or paths to include. If None, all files are included.", default=None)),
    blacklist=(Optional[List[str]], Field(description="A list of file extensions or paths to exclude. If None, no files are excluded.", default=None))
)

CreateIssueOnProject = create_model(
    "CreateIssueOnProject",
    board_repo=(str, Field(description="The organization and repository for the board (project). Example: 'org-name/repo-name'")),
    project_title=(str, Field(description="The title of the project to which the issue will be added")),
    title=(str, Field(description="Title for the newly created issue")),
    body=(str, Field(description="Body text for the newly created issue")),
    fields=(Optional[Dict[str, str]], Field(description="Additional key value pairs for issue field configurations", default=None)),
    issue_repo=(Optional[str], Field(description="The issue's organization and repository to link issue on the board. Example: 'org-name/repo-name-2'", default=None))
)

UpdateIssueOnProject = create_model(
    "UpdateIssueOnProject",
    board_repo=(str, Field(description="The organization and repository for the board (project). Example: 'org-name/repo-name'")),
    issue_number=(str, Field(description="The unique number of the issue to update")),
    project_title=(str, Field(description="The title of the project from which to fetch the issue")),
    title=(str, Field(description="New title to set for the issue")),
    body=(str, Field(description="New body content to set for the issue")),
    fields=(Optional[Dict[str, str]], Field(description="A dictionary of additional field values by field names to update. Provide empty string to clear field", default=None)),
    issue_repo=(Optional[str], Field(description="The issue's organization and repository to link issue on the board. Example: 'org-name/repo-name-2'", default=None))
)

GetCommits = create_model(
    "GetCommits",
    repo_name=(Optional[str], Field(default=None, description="Name of the repository (e.g., 'owner/repo'). If None, uses the default repository.")),
    sha=(Optional[str], Field(description="The commit SHA or branch name to start listing commits from", default=None)),
    path=(Optional[str], Field(description="The file path to filter commits by", default=None)),
    since=(Optional[str], Field(description="Only commits after this date will be returned (ISO format)", default=None)),
    until=(Optional[str], Field(description="Only commits before this date will be returned (ISO format)", default=None)),
    author=(Optional[str], Field(description="The author of the commits", default=None)),
    max_count=(Optional[int], Field(description="Maximum number of commits to return (default: 30)", default=30))
)

GetCommitChanges = create_model(
    "GetCommitChanges",
    sha=(str, Field(description="The commit SHA to get changed files for")),
    repo_name=(Optional[str], Field(default=None, description="Name of the repository (e.g., 'owner/repo'). If None, uses the default repository."))
)

GetCommitsDiff = create_model(
    "GetCommitsDiff",
    base_sha=(str, Field(description="The base commit SHA to compare from")),
    head_sha=(str, Field(description="The head commit SHA to compare to")),
    repo_name=(Optional[str], Field(default=None, description="Name of the repository (e.g., 'owner/repo'). If None, uses the default repository."))
)

ApplyGitPatch = create_model(
    "ApplyGitPatch",
    patch_content=(str, Field(description="The git patch content in unified diff format")),
    commit_message=(Optional[str], Field(description="Commit message for the patch application", default="Apply git patch")),
    repo_name=(Optional[str], Field(default=None, description="Name of the repository (e.g., 'owner/repo'). If None, uses the default repository."))
)

ApplyGitPatchFromArtifact = create_model(
    "ApplyGitPatchFromArtifact",
    bucket_name=(str, Field(description="Name of the artifact bucket containing the patch file")),
    file_name=(str, Field(description="Name of the patch file to download and apply")),
    commit_message=(Optional[str], Field(description="Commit message for the patch application", default="Apply git patch from artifact")),
    repo_name=(Optional[str], Field(default=None, description="Name of the repository (e.g., 'owner/repo'). If None, uses the default repository."))
)

TriggerWorkflow = create_model(
    "TriggerWorkflow",
    workflow_id=(str, Field(description="The ID or file name of the workflow to trigger (e.g., 'build.yml', '1234567')")),
    ref=(str, Field(description="The branch or tag reference to trigger the workflow on (e.g., 'main', 'v1.0.0')")),
    inputs=(Optional[Dict[str, Any]], Field(description="Optional inputs for the workflow, as defined in the workflow file", default=None)),
    repo_name=(Optional[str], Field(default=None, description="Name of the repository (e.g., 'owner/repo'). If None, uses the default repository."))
)

GetWorkflowStatus = create_model(
    "GetWorkflowStatus",
    run_id=(str, Field(description="The ID of the workflow run to get status for")),
    repo_name=(Optional[str], Field(description="Name of the repository to get workflow status from", default=None))
)

GetWorkflowLogs = create_model(
    "GetWorkflowLogs",
    run_id=(str, Field(description="The ID of the workflow run to get logs for")),
    repo_name=(Optional[str], Field(description="Name of the repository to get workflow logs from", default=None))
)

GenericGithubAPICall = create_model(
    "GenericGithubAPICall",
    method=(str, Field(description="The GitHub API method to call (e.g., 'get_repo', 'get_user')")),
    method_kwargs=(Optional[Dict[str, Any]], Field(description="Keyword arguments for the API method as a dictionary"))
)

ListProjectIssues = create_model(
    "ListProjectIssues",
    board_repo=(str, Field(description="The organization and repository for the board (project). Example: 'org-name/repo-name'")),
    project_number=(int, Field(description="The project number as shown in the project URL")),
    items_count=(Optional[int], Field(description="Maximum number of items to retrieve", default=100))
)

SearchProjectIssues = create_model(
    "SearchProjectIssues",
    board_repo=(str, Field(description="The organization and repository for the board (project). Example: 'org-name/repo-name'")),
    project_number=(int, Field(description="The project number as shown in the project URL")),
    search_query=(str, Field(description="Search query for filtering issues. Examples: 'status:In Progress', 'release:v1.0'")),
    items_count=(Optional[int], Field(description="Maximum number of items to retrieve", default=100))
)

ListProjectViews = create_model(
    "ListProjectViews",
    board_repo=(str, Field(description="The organization and repository for the board (project). Format: 'org-name/repo-name'")),
    project_number=(int, Field(description="The project number (visible in the project URL)")),
    first=(Optional[int], Field(description="Number of views to fetch", default=100)),
    after=(Optional[str], Field(description="Cursor for pagination", default=None))
)

GetProjectItemsByView = create_model(
    "GetProjectItemsByView",
    board_repo=(str, Field(description="The organization and repository for the board (project). Format: 'org-name/repo-name'")),
    project_number=(int, Field(description="The project number (visible in the project URL)")),
    view_number=(int, Field(description="The view number to filter by")),
    first=(Optional[int], Field(description="Number of items to fetch", default=100)),
    after=(Optional[str], Field(description="Cursor for pagination", default=None)),
    filter_by=(Optional[Dict[str, Dict[str, str]]], Field(description="Dictionary containing filter parameters. Format: {'field_name': {'value': 'value'}}", default=None))
)