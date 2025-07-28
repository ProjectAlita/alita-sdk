from __future__ import annotations
import re
import fnmatch
import tiktoken
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, model_validator

from github import Auth, Github, GithubIntegration, Repository
from github.Consts import DEFAULT_BASE_URL
from langchain_core.tools import ToolException

from .schemas import (
    GitHubAuthConfig,
    GitHubRepoConfig,
)

from .schemas import (
    GitHubAuthConfig,
    GitHubRepoConfig,
    NoInput,
    BranchName,
    CreateBranchName,
    DirectoryPath,
    ReadFile,
    UpdateFile,
    CreateFile,
    DeleteFile,
    GetIssue,
    GetPR,
    CreatePR,
    CommentOnIssue,
    SearchIssues,
    CreateIssue,
    UpdateIssue,
    GetCommits,
    GetCommitChanges,
    GetCommitsDiff,
    ApplyGitPatch,
    ApplyGitPatchFromArtifact,
    TriggerWorkflow,
    GetWorkflowStatus,
    GetWorkflowLogs,
    GenericGithubAPICall
)

# Import prompts for tools
from .tool_prompts import (
    CREATE_FILE_PROMPT,
    UPDATE_FILE_PROMPT,
    CREATE_ISSUE_PROMPT,
    UPDATE_ISSUE_PROMPT,
)

from langchain_community.tools.github.prompt import (
    DELETE_FILE_PROMPT,
    OVERVIEW_EXISTING_FILES_IN_MAIN,
    LIST_BRANCHES_IN_REPO_PROMPT,
    SET_ACTIVE_BRANCH_PROMPT,
    CREATE_BRANCH_PROMPT,
    GET_FILES_FROM_DIRECTORY_PROMPT,
    SEARCH_ISSUES_AND_PRS_PROMPT,
    READ_FILE_PROMPT,
    GET_ISSUES_PROMPT,
    GET_ISSUE_PROMPT,
    COMMENT_ON_ISSUE_PROMPT,
    LIST_PRS_PROMPT,
    GET_PR_PROMPT,
    LIST_PULL_REQUEST_FILES,
    CREATE_PULL_REQUEST_PROMPT
)


class GitHubClient(BaseModel):
    """Client for interacting with the GitHub REST API."""

    # Config for Pydantic model
    class Config:
        arbitrary_types_allowed = True

    # Public attributes that can be serialized/deserialized
    github_repository: str = Field(default="")
    active_branch: str = Field(default="")
    github_base_branch: str = Field(default="main")
    github_base_url: str = Field(default=DEFAULT_BASE_URL)

    # Using optional variables with None defaults instead of PrivateAttr
    github_api: Optional[Github] = Field(default=None, exclude=True)
    github_repo_instance: Optional[Repository.Repository] = Field(default=None, exclude=True)

    # Adding auth config and repo config as optional fields for initialization
    auth_config: Optional[GitHubAuthConfig] = Field(default=None, exclude=True)
    repo_config: Optional[GitHubRepoConfig] = Field(default=None, exclude=True)
    
    # Alita instance
    alita: Optional[Any] = Field(default=None, exclude=True)

    @model_validator(mode='before')
    def initialize_github_client(cls, values):
        """
        Initialize the GitHub client after the model is created.
        This replaces the need for a custom __init__ method.

        Returns:
            The initialized values dictionary
        """

        if values.get("repo_config"):
            values["github_repository"] = values["repo_config"].github_repository
            values["active_branch"] = values["repo_config"].active_branch
            values["github_base_branch"] = values["repo_config"].github_base_branch

        # If auth_config is provided, update base URL and set up authentication
        if values.get("auth_config"):
            values["github_base_url"] = values["auth_config"].github_base_url or DEFAULT_BASE_URL

            # Set up authentication
            auth = None
            if values["auth_config"].github_access_token:
                auth = Auth.Token(values["auth_config"].github_access_token.get_secret_value())
            elif values["auth_config"].github_username and values["auth_config"].github_password:
                auth = Auth.Login(values["auth_config"].github_username, values["auth_config"].github_password.get_secret_value())
            elif values["auth_config"].github_app_id and values["auth_config"].github_app_private_key:
                # Format the private key correctly
                private_key = values["auth_config"].github_app_private_key.get_secret_value()
                header = "-----BEGIN RSA PRIVATE KEY-----"
                footer = "-----END RSA PRIVATE KEY-----"

                if header not in private_key:
                    key_body = private_key
                    body = key_body.replace(" ", "\n")
                    private_key = f"{header}\n{body}\n{footer}"

                auth = Auth.AppAuth(values["auth_config"].github_app_id, private_key)

            # Initialize GitHub client
            if auth is None:
                values["github_api"] = Github(base_url=values["github_base_url"])
            elif values["auth_config"].github_app_id and values["auth_config"].github_app_private_key:
                gi = GithubIntegration(base_url=values["github_base_url"], auth=auth)
                installation = gi.get_installations()[0]
                values["github_api"] = installation.get_github_for_installation()
            else:
                values["github_api"] = Github(base_url=values["github_base_url"], auth=auth)

            # Get repository instance
            if values.get("github_repository"):
                values["github_repo_instance"] = values["github_api"].get_repo(values["github_repository"])
        else:
            # Initialize with default authentication if no auth_config provided
            values["github_api"] = Github(base_url=values.get("github_base_url", DEFAULT_BASE_URL))
            if values.get("github_repository"):
                values["github_repo_instance"] = values["github_api"].get_repo(values["github_repository"])

        return values

    @staticmethod
    def clean_repository_name(repo_link: str) -> str:
        """
        Clean and format a repository name from various input formats.

        Args:
            repo_link: Repository link or name in various formats

        Returns:
            Cleaned repository name in format "owner/repo"

        Raises:
            ToolException: If the repository name is invalid
        """
        match = re.match(r"^(?:https?://[^/]+/|git@[^:]+:)?([^/]+/[^/]+?)(?:\.git)?$", repo_link)
        if not match:
            raise ToolException("Repository field should be in '<owner>/<repo>' format.")
        return match.group(1)

    def _get_files(self, directory_path: str, ref: str, repo_name: Optional[str] = None) -> List[str]:
        """
        Get all files in a directory recursively.

        Args:
            directory_path: Path to the directory
            ref: Branch or commit reference
            repo_name: Optional repository name to override default

        Returns:
            List of file paths
        """
        from github import GithubException

        try:
            repo = self.github_api.get_repo(repo_name) if repo_name else self.github_repo_instance
            contents = repo.get_contents(directory_path, ref=ref)
        except GithubException as e:
            return f"Error: status code {e.status}, {e.message}"

        files = []
        while contents:
            file_content = contents.pop(0)
            if file_content.type == "dir":
                try:
                    directory_contents = repo.get_contents(file_content.path, ref=ref)
                    contents.extend(directory_contents)
                except GithubException:
                    pass
            else:
                files.append(file_content)

        return [file.path for file in files]

    def get_files_from_directory(self, directory_path: str, repo_name: Optional[str] = None) -> str:
        """
        Recursively fetches files from a directory in the repo.

        Parameters:
            directory_path (str): Path to the directory
            repo_name (Optional[str]): Name of the repository in format 'owner/repo'

        Returns:
            str: List of file paths, or an error message.
        """
        return self._get_files(directory_path, self.active_branch, repo_name)

    def get_issue(self, issue_number: int, repo_name: Optional[str] = None) -> str:
        """
        Fetches information about a specific issue.

        Parameters:
            issue_number (str): Number of the issue to fetch
            repo_name (Optional[str]): Name of the repository in format 'owner/repo'

        Returns:
            str: A dictionary containing information about the issue.
        """
        try:
            repo = self.github_api.get_repo(repo_name) if repo_name else self.github_repo_instance
            issue = repo.get_issue(int(issue_number))
            issue_data = {
                "number": issue.number,
                "title": issue.title,
                "body": issue.body,
                "state": issue.state,
                "url": issue.html_url,
                "created_at": issue.created_at.isoformat(),
                "updated_at": issue.updated_at.isoformat(),
                "comments": issue.comments,
                "labels": [label.name for label in issue.labels],
                "assignees": [assignee.login for assignee in issue.assignees]
            }
            return issue_data
        except Exception as e:
            return f"Failed to get issue: {str(e)}"

    def list_files_in_main_branch(self, repo_name: Optional[str] = None) -> str:
        """
        Fetches all files in the main branch of the repo.

        Parameters:
            repo_name (Optional[str]): Name of the repository in format 'owner/repo'

        Returns:
            str: A plaintext report containing the paths and names of the files.
        """
        return self._get_files("", self.github_base_branch, repo_name)

    def list_files_in_bot_branch(self, repo_name: Optional[str] = None) -> str:
        """
        Fetches all files in the current working branch.

        Parameters:
            repo_name (Optional[str]): Name of the repository in format 'owner/repo'

        Returns:
            str: A plaintext report containing the paths and names of the files.
        """
        return self._get_files("", self.active_branch, repo_name)

    def get_commits(
            self,
            sha: Optional[str] = None,
            path: Optional[str] = None,
            since: Optional[str] = None,
            until: Optional[str] = None,
            author: Optional[str] = None,
            repo_name: Optional[str] = None,
            max_count: Optional[int] = 30,
    ) -> str:
        """
        Retrieves a list of commits from the repository.

        Parameters:
            sha (Optional[str]): The commit SHA to start listing commits from.
            path (Optional[str]): The file path to filter commits by.
            since (Optional[str]): Only commits after this date (ISO format) will be returned.
            until (Optional[str]): Only commits before this date (ISO format) will be returned.
            author (Optional[str]): The author of the commits.
            repo_name (Optional[str]): Name of the repository in format 'owner/repo'.
            max_count (Optional[int]): Maximum number of commits to return (default: 30).

        Returns:
            str: A list of commit data or an error message.
        """
        try:
            # Prepare the parameters for the API call
            params = {
                "sha": sha,
                "path": path,
                "since": datetime.fromisoformat(since) if since else None,
                "until": datetime.fromisoformat(until) if until else None,
                "author": author if isinstance(author, str) else None,
            }
            # Remove None values from the parameters
            params = {key: value for key, value in params.items() if value}

            # Call the GitHub API to get commits
            repo = self.github_api.get_repo(repo_name) if repo_name else self.github_repo_instance
            commits = repo.get_commits(**params)

            # Convert the commits to a list of dictionaries for easier processing
            # Limit the number of commits based on max_count
            commit_list = []
            count = 0
            for commit in commits:
                if count >= max_count:
                    break
                commit_list.append({
                    "sha": commit.sha,
                    "author": commit.commit.author.name,
                    "date": commit.commit.author.date.isoformat(),
                    "message": commit.commit.message,
                    "url": commit.html_url,
                })
                count += 1

            return commit_list

        except Exception as e:
            # Return error as JSON instead of plain text
            return {"error": str(e), "message": f"Unable to retrieve commits due to error: {str(e)}"}

    def get_commit_changes(self, sha: str, repo_name: Optional[str] = None) -> str:
        """
        Retrieves the files changed in a specific commit.

        Parameters:
            sha (str): The commit SHA to get changed files for.
            repo_name (Optional[str]): Name of the repository in format 'owner/repo'.

        Returns:
            str: A list of changed files with their status and changes or an error message.
        """
        try:
            # Get the repository
            repo = self.github_api.get_repo(repo_name) if repo_name else self.github_repo_instance
            
            # Get the specific commit
            commit = repo.get_commit(sha)
            
            # Extract changed files information
            changed_files = []
            for file in commit.files:
                file_info = {
                    "filename": file.filename,
                    "status": file.status,  # added, modified, removed, renamed
                    "additions": file.additions,
                    "deletions": file.deletions,
                    "changes": file.changes,
                    "patch": file.patch if hasattr(file, 'patch') and file.patch else None,
                    "blob_url": file.blob_url if hasattr(file, 'blob_url') else None,
                    "raw_url": file.raw_url if hasattr(file, 'raw_url') else None
                }
                
                # Add previous filename for renamed files
                if file.status == "renamed" and hasattr(file, 'previous_filename'):
                    file_info["previous_filename"] = file.previous_filename
                    
                changed_files.append(file_info)
            
            result = {
                "commit_sha": commit.sha,
                "commit_message": commit.commit.message,
                "author": commit.commit.author.name,
                "date": commit.commit.author.date.isoformat(),
                "total_files_changed": len(changed_files),
                "total_additions": sum(f["additions"] for f in changed_files),
                "total_deletions": sum(f["deletions"] for f in changed_files),
                "files": changed_files
            }
            
            return result

        except Exception as e:
            # Return error as JSON instead of plain text
            return {"error": str(e), "message": f"Unable to retrieve commit changes due to error: {str(e)}"}
        
    def get_commits_diff(self, base_sha: str, head_sha: str, repo_name: Optional[str] = None) -> str:
        """
        Retrieves the diff between two commits.

        Parameters:
            base_sha (str): The base commit SHA to compare from.
            head_sha (str): The head commit SHA to compare to.
            repo_name (Optional[str]): Name of the repository in format 'owner/repo'.

        Returns:
            str: A detailed diff comparison between the two commits or an error message.
        """
        try:
            # Get the repository
            repo = self.github_api.get_repo(repo_name) if repo_name else self.github_repo_instance
            
            # Get the comparison between the two commits
            comparison = repo.compare(base_sha, head_sha)
            
            # Extract comparison information
            diff_info = {
                "base_commit": {
                    "sha": comparison.base_commit.sha,
                    "message": comparison.base_commit.commit.message,
                    "author": comparison.base_commit.commit.author.name,
                    "date": comparison.base_commit.commit.author.date.isoformat()
                },
                "head_commit": {
                    "sha": comparison.head_commit.sha,
                    "message": comparison.head_commit.commit.message,
                    "author": comparison.head_commit.commit.author.name,
                    "date": comparison.head_commit.commit.author.date.isoformat()
                },
                "status": comparison.status,  # ahead, behind, identical, or diverged
                "ahead_by": comparison.ahead_by,
                "behind_by": comparison.behind_by,
                "total_commits": comparison.total_commits,
                "commits": [],
                "files": []
            }
            
            # Get commits in the comparison
            for commit in comparison.commits:
                commit_info = {
                    "sha": commit.sha,
                    "message": commit.commit.message,
                    "author": commit.commit.author.name,
                    "date": commit.commit.author.date.isoformat(),
                    "url": commit.html_url
                }
                diff_info["commits"].append(commit_info)
            
            # Get changed files information
            for file in comparison.files:
                file_info = {
                    "filename": file.filename,
                    "status": file.status,  # added, modified, removed, renamed
                    "additions": file.additions,
                    "deletions": file.deletions,
                    "changes": file.changes,
                    "patch": file.patch if hasattr(file, 'patch') and file.patch else None,
                    "blob_url": file.blob_url if hasattr(file, 'blob_url') else None,
                    "raw_url": file.raw_url if hasattr(file, 'raw_url') else None
                }
                
                # Add previous filename for renamed files
                if file.status == "renamed" and hasattr(file, 'previous_filename'):
                    file_info["previous_filename"] = file.previous_filename
                    
                diff_info["files"].append(file_info)
            
            # Add summary statistics
            diff_info["summary"] = {
                "total_files_changed": len(diff_info["files"]),
                "total_additions": sum(f["additions"] for f in diff_info["files"]),
                "total_deletions": sum(f["deletions"] for f in diff_info["files"])
            }
            
            return diff_info

        except Exception as e:
            # Return error as JSON instead of plain text
            return {"error": str(e), "message": f"Unable to retrieve diff between commits due to error: {str(e)}"}
        
    def apply_git_patch_from_file(self, bucket_name: str, file_name: str, commit_message: Optional[str] = "Apply git patch", repo_name: Optional[str] = None) -> str:
        """Applies a git patch from a file stored in a specified bucket.

        Args:
            bucket_name (str): The name of the bucket where the patch file is stored.
            file_name (str): The name of the patch file to apply.
            commit_message (Optional[str], optional): The commit message for the patch application. Defaults to "Apply git patch".
            repo_name (Optional[str], optional): The name of the repository to apply the patch to. Defaults to None.

        Returns:
            str: A summary of the applied changes or an error message.
        """
        try:
            patch_content = self.alita.download_artifact(bucket_name, file_name)
            
            if not patch_content:
                return {"error": "Patch file not found", "message": f"Patch file '{file_name}' not found in bucket '{bucket_name}'."}
            
            # Convert bytes to string if necessary
            if isinstance(patch_content, bytes):
                patch_content = patch_content.decode('utf-8')
            elif not isinstance(patch_content, str):
                return {"error": "Invalid patch content", "message": f"Patch file '{file_name}' contains invalid content type."}
            
            # Apply the git patch using the content
            return self.apply_git_patch(patch_content, commit_message, repo_name)
        except Exception as e:
            return {"error": str(e), "message": f"Unable to download patch file: {str(e)}"}

    def apply_git_patch(self, patch_content: str, commit_message: Optional[str] = "Apply git patch", repo_name: Optional[str] = None) -> str:
        """
        Applies a git patch to the repository by parsing the unified diff format and updating files accordingly.

        Parameters:
            patch_content (str): The git patch content in unified diff format
            commit_message (Optional[str]): Commit message for the patch application
            repo_name (Optional[str]): Name of the repository in format 'owner/repo'

        Returns:
            str: A summary of applied changes or error message
        """
        import re
        
        try:
            repo = self.github_api.get_repo(repo_name) if repo_name else self.github_repo_instance
            branch = self.active_branch

            if branch == self.github_base_branch:
                return {
                    "error": "Cannot apply patch",
                    "message": f"You're attempting to commit directly to the {self.github_base_branch} branch, which is protected. Please create a new branch and try again."
                }

            # Parse the patch content to extract file changes
            changes = self._parse_git_patch(patch_content)
            
            if not changes:
                return {
                    "error": "No valid changes found",
                    "message": "The patch content does not contain any valid file changes."
                }

            applied_changes = []
            failed_changes = []

            for change in changes:
                try:
                    if change['operation'] == 'create':
                        # Create new file
                        repo.create_file(
                            path=change['file_path'],
                            message=f"{commit_message} - Create {change['file_path']}",
                            content=change['new_content'],
                            branch=branch
                        )
                        applied_changes.append(f"Created: {change['file_path']}")

                    elif change['operation'] == 'delete':
                        # Delete file
                        try:
                            file = repo.get_contents(change['file_path'], ref=branch)
                            repo.delete_file(
                                path=change['file_path'],
                                message=f"{commit_message} - Delete {change['file_path']}",
                                sha=file.sha,
                                branch=branch
                            )
                            applied_changes.append(f"Deleted: {change['file_path']}")
                        except Exception:
                            failed_changes.append(f"Failed to delete {change['file_path']} - file not found")

                    elif change['operation'] == 'modify':
                        # Modify existing file
                        try:
                            file = repo.get_contents(change['file_path'], ref=branch)
                            current_content = file.decoded_content.decode("utf-8")
                            
                            # Apply the patch changes
                            new_content = self._apply_patch_to_content(current_content, change['hunks'])
                            
                            if new_content != current_content:
                                repo.update_file(
                                    path=change['file_path'],
                                    message=f"{commit_message} - Update {change['file_path']}",
                                    content=new_content,
                                    sha=file.sha,
                                    branch=branch
                                )
                                applied_changes.append(f"Modified: {change['file_path']}")
                            else:
                                failed_changes.append(f"No changes applied to {change['file_path']} - patch may not match current content")
                        except Exception as e:
                            failed_changes.append(f"Failed to modify {change['file_path']}: {str(e)}")

                    elif change['operation'] == 'rename':
                        # Handle file rename (delete old, create new)
                        try:
                            # Delete old file
                            old_file = repo.get_contents(change['old_file_path'], ref=branch)
                            old_content = old_file.decoded_content.decode("utf-8")
                            
                            # Apply changes to content if there are any
                            if change.get('hunks'):
                                new_content = self._apply_patch_to_content(old_content, change['hunks'])
                            else:
                                new_content = old_content
                            
                            # Create new file
                            repo.create_file(
                                path=change['file_path'],
                                message=f"{commit_message} - Rename {change['old_file_path']} to {change['file_path']}",
                                content=new_content,
                                branch=branch
                            )
                            
                            # Delete old file
                            repo.delete_file(
                                path=change['old_file_path'],
                                message=f"{commit_message} - Remove old file {change['old_file_path']}",
                                sha=old_file.sha,
                                branch=branch
                            )
                            
                            applied_changes.append(f"Renamed: {change['old_file_path']} → {change['file_path']}")
                        except Exception as e:
                            failed_changes.append(f"Failed to rename {change.get('old_file_path', 'unknown')} to {change['file_path']}: {str(e)}")

                except Exception as e:
                    failed_changes.append(f"Failed to process {change.get('file_path', 'unknown file')}: {str(e)}")

            # Return summary
            result = {
                "success": len(applied_changes) > 0,
                "applied_changes": applied_changes,
                "failed_changes": failed_changes,
                "total_changes": len(changes),
                "successful_changes": len(applied_changes),
                "failed_count": len(failed_changes)
            }

            if failed_changes:
                result["message"] = f"Patch partially applied. {len(applied_changes)} successful, {len(failed_changes)} failed."
            else:
                result["message"] = f"Patch successfully applied. {len(applied_changes)} changes made."

            return result

        except Exception as e:
            return {
                "error": str(e),
                "message": f"Unable to apply git patch due to error: {str(e)}"
            }

    def _parse_git_patch(self, patch_content: str) -> List[Dict]:
        """
        Parse git patch content in unified diff format and extract file changes.
        
        Parameters:
            patch_content (str): The patch content to parse
            
        Returns:
            List[Dict]: List of change dictionaries
        """
        import re
        
        changes = []
        lines = patch_content.strip().split('\n')
        i = 0
        
        while i < len(lines):
            line = lines[i]
            
            # Look for diff --git lines
            if line.startswith('diff --git'):
                change = self._parse_file_change(lines, i)
                if change:
                    changes.append(change)
                    i = change.get('next_index', i + 1)
                else:
                    i += 1
            else:
                i += 1
                
        return changes

    def _parse_file_change(self, lines: List[str], start_index: int) -> Optional[Dict]:
        """
        Parse a single file change from patch lines.
        
        Parameters:
            lines (List[str]): All patch lines
            start_index (int): Starting index for this file change
            
        Returns:
            Optional[Dict]: Parsed file change or None if invalid
        """
        import re
        
        if start_index >= len(lines):
            return None
            
        diff_line = lines[start_index]
        
        # Extract file paths from diff line
        match = re.match(r'diff --git a/(.+) b/(.+)', diff_line)
        if not match:
            return None
            
        old_path = match.group(1)
        new_path = match.group(2)
        
        change = {
            'old_file_path': old_path,
            'file_path': new_path,
            'hunks': [],
            'next_index': start_index + 1
        }
        
        i = start_index + 1
        
        # Process header lines (index, ---, +++, etc.)
        while i < len(lines):
            line = lines[i]
            
            if line.startswith('new file mode'):
                change['operation'] = 'create'
            elif line.startswith('deleted file mode'):
                change['operation'] = 'delete'
            elif line.startswith('rename from'):
                change['operation'] = 'rename'
            elif line.startswith('index '):
                pass  # Skip index lines
            elif line.startswith('--- '):
                pass  # Skip old file reference
            elif line.startswith('+++ '):
                pass  # Skip new file reference
            elif line.startswith('@@'):
                # Found a hunk, parse it
                hunk, next_i = self._parse_hunk(lines, i)
                if hunk:
                    change['hunks'].append(hunk)
                i = next_i
                continue
            elif line.startswith('diff --git') or line.startswith('Binary files'):
                # Start of next file or binary file
                break
            elif line.strip() == '':
                pass  # Skip empty lines
            else:
                # Unknown line, continue
                pass
                
            i += 1
            
        # Determine operation if not set
        if 'operation' not in change:
            if old_path == new_path:
                change['operation'] = 'modify'
            else:
                change['operation'] = 'rename'
                
        change['next_index'] = i
        
        # For new files, extract content from hunks
        if change['operation'] == 'create' and change['hunks']:
            content_lines = []
            for hunk in change['hunks']:
                for line in hunk['lines']:
                    if line.startswith('+') and not line.startswith('+++'):
                        content_lines.append(line[1:])  # Remove + prefix
            change['new_content'] = '\n'.join(content_lines)
            
        return change

    def _parse_hunk(self, lines: List[str], start_index: int) -> Tuple[Optional[Dict], int]:
        """
        Parse a single hunk from patch lines.
        
        Parameters:
            lines (List[str]): All patch lines  
            start_index (int): Starting index for this hunk
            
        Returns:
            Tuple[Optional[Dict], int]: Parsed hunk and next index
        """
        import re
        
        if start_index >= len(lines):
            return None, start_index + 1
            
        hunk_header = lines[start_index]
        
        # Parse hunk header: @@ -old_start,old_count +new_start,new_count @@
        match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', hunk_header)
        if not match:
            return None, start_index + 1
            
        old_start = int(match.group(1))
        old_count = int(match.group(2)) if match.group(2) else 1
        new_start = int(match.group(3))
        new_count = int(match.group(4)) if match.group(4) else 1
        
        hunk = {
            'old_start': old_start,
            'old_count': old_count,
            'new_start': new_start,
            'new_count': new_count,
            'lines': []
        }
        
        i = start_index + 1
        
        # Collect hunk lines
        while i < len(lines):
            line = lines[i]
            
            if line.startswith('@@') or line.startswith('diff --git') or line.startswith('Binary files'):
                # Start of next hunk or file
                break
            elif line.startswith(' ') or line.startswith('+') or line.startswith('-'):
                # Context, addition, or deletion line
                hunk['lines'].append(line)
            elif line.strip() == '':
                # Empty line in hunk
                hunk['lines'].append(line)
            else:
                # Unknown line, stop parsing this hunk
                break
                
            i += 1
            
        return hunk, i

    def _apply_patch_to_content(self, original_content: str, hunks: List[Dict]) -> str:
        """
        Apply patch hunks to original content.
        
        Parameters:
            original_content (str): Original file content
            hunks (List[Dict]): List of patch hunks
            
        Returns:
            str: Modified content
        """
        if not hunks:
            return original_content
            
        lines = original_content.split('\n')
        result_lines = []
        
        # Sort hunks by line number
        sorted_hunks = sorted(hunks, key=lambda h: h['old_start'])
        
        current_line = 0
        
        for hunk in sorted_hunks:
            # Add lines before this hunk
            while current_line < hunk['old_start'] - 1:
                if current_line < len(lines):
                    result_lines.append(lines[current_line])
                current_line += 1
                
            # Apply hunk changes
            old_line_in_hunk = 0
            
            for patch_line in hunk['lines']:
                if patch_line.startswith(' '):
                    # Context line - should match original
                    context_line = patch_line[1:]
                    if current_line < len(lines):
                        result_lines.append(lines[current_line])
                        current_line += 1
                    old_line_in_hunk += 1
                elif patch_line.startswith('-'):
                    # Deletion - skip original line
                    current_line += 1
                    old_line_in_hunk += 1
                elif patch_line.startswith('+'):
                    # Addition - add new line
                    result_lines.append(patch_line[1:])
                    
        # Add remaining lines
        while current_line < len(lines):
            result_lines.append(lines[current_line])
            current_line += 1
            
        return '\n'.join(result_lines)

    def get_pull_request(self, pr_number: str, repo_name: Optional[str] = None) -> str:
        """
        Fetches information about a specific pull request.

        Parameters:
            pr_number (str): Number of the pull request to fetch
            repo_name (Optional[str]): Name of the repository in format 'owner/repo'

        Returns:
            str: A dictionary containing information about the pull request.
        """
        max_tokens = 2000
        try:
            repo = self.github_api.get_repo(repo_name) if repo_name else self.github_repo_instance
            pull = repo.get_pull(number=int(pr_number))
            total_tokens = 0

            def get_tokens(text: str) -> int:
                return len(tiktoken.get_encoding("cl100k_base").encode(text))

            def add_to_dict(data_dict: Dict[str, Any], key: str, value: Any) -> None:
                nonlocal total_tokens  # Declare total_tokens as nonlocal
                # Convert value to string only for token counting if it's not already a string
                value_str = str(value) if not isinstance(value, str) else value
                tokens = get_tokens(value_str)
                if total_tokens + tokens <= max_tokens:
                    data_dict[key] = value
                    total_tokens += tokens

            response_dict: Dict[str, Any] = {}
            add_to_dict(response_dict, "title", pull.title)
            add_to_dict(response_dict, "number", int(pr_number))  # Ensure number is an integer
            add_to_dict(response_dict, "body", str(pull.body))
            add_to_dict(response_dict, "pr_url", str(pull.html_url))

            comments: List[str] = []
            page = 0
            while len(comments) <= 10:
                comments_page = pull.get_issue_comments().get_page(page)
                if len(comments_page) == 0:
                    break
                for comment in comments_page:
                    comment_str = str({"body": comment.body, "user": comment.user.login})
                    if total_tokens + get_tokens(comment_str) > max_tokens:
                        break
                    comments.append(comment_str)
                    total_tokens += get_tokens(comment_str)
                page += 1
            add_to_dict(response_dict, "comments", str(comments))

            commits: List[str] = []
            page = 0
            while len(commits) <= 10:
                commits_page = pull.get_commits().get_page(page)
                if len(commits_page) == 0:
                    break
                for commit in commits_page:
                    commit_str = str({"message": commit.commit.message})
                    if total_tokens + get_tokens(commit_str) > max_tokens:
                        break
                    commits.append(commit_str)
                    total_tokens += get_tokens(commit_str)
                page += 1
            add_to_dict(response_dict, "commits", str(commits))
            return response_dict
        except Exception as e:
            return f"Failed to get pull request: {str(e)}"

    def list_pull_request_diffs(self, pr_number: int, repo_name: Optional[str] = None) -> str:
        """
        Fetches the files included in a pull request.

        Parameters:
            pr_number (int): Number of the pull request to fetch diffs for
            repo_name (Optional[str]): Name of the repository in format 'owner/repo'. If None, uses the default repository instance.

        Returns:
            str: A JSON string with files and patches included in the pull request.
        """
        try:
            # Grab PR
            repo = self.github_api.get_repo(repo_name) if repo_name else self.github_repo_instance
            pr = repo.get_pull(int(pr_number))
            files = pr.get_files()
            data = []
            for file in files:
                path = file.filename
                patch = file.patch
                data.append(
                    {
                        "path": path,
                        "patch": patch,
                        "filename": path,
                        "status": file.status,
                        "additions": file.additions,
                        "deletions": file.deletions,
                        "changes": file.changes
                    }
                )
            return data
        except Exception as e:
            # Return error as JSON instead of plain string
            return {"error": str(e), "message": f"Failed to get pull request diffs: {str(e)}"}

    def create_branch(self, proposed_branch_name: str, repo_name: Optional[str] = None) -> str:
        """
        Create a new branch, and set it as the active bot branch.
        Equivalent to `git switch -c proposed_branch_name`
        If the proposed branch already exists, we append _v1 then _v2...
        until a unique name is found.

        Parameters:
            proposed_branch_name (str): Name to use for the new branch
            repo_name (Optional[str]): Name of the repository in format 'owner/repo'

        Returns:
            str: A plaintext success message.
        """
        from github import GithubException

        try:
            repo = self.github_api.get_repo(repo_name) if repo_name else self.github_repo_instance
            i = 0
            new_branch_name = proposed_branch_name

            # Get base branch - if repo_name is specified, use github_base_branch
            base_branch_name = self.github_base_branch if repo_name else (self.active_branch if self.active_branch else self.github_base_branch)
            base_branch = repo.get_branch(base_branch_name)

            for i in range(1000):
                try:
                    repo.create_git_ref(
                        ref=f"refs/heads/{new_branch_name}", sha=base_branch.commit.sha
                    )

                    # Only set active branch if using the default repository
                    if not repo_name:
                        self.active_branch = new_branch_name

                    return (
                        f"Branch '{new_branch_name}' created successfully" +
                        ("" if repo_name else ", and set as current active branch.")
                    )
                except GithubException as e:
                    if (e.status == 422 and "Reference already exists" in e.data["message"]):
                        if i == 0:
                            new_branch_name = f"{proposed_branch_name}_v1"
                        else:
                            new_branch_name = f"{proposed_branch_name}_v{i+1}"
                    else:
                        return f"Unable to create branch due to error: {str(e)}"

            return (
                "Unable to create branch. "
                "At least 1000 branches exist with named derived from "
                f"proposed_branch_name: `{proposed_branch_name}`"
            )
        except Exception as e:
            return f"Failed to create branch: {str(e)}"

    def create_file(self, file_path: str, file_contents: str, repo_name: Optional[str] = None) -> str:
        """
        Creates a new file on the GitHub repo
        Parameters:
            file_path (str): The path of the file to be created
            file_contents (str): The content of the file to be created
            repo_name (Optional[str]): Name of the repository in format 'owner/repo'

        Returns:
            str: A success or failure message
        """
        try:
            repo = self.github_api.get_repo(repo_name) if repo_name else self.github_repo_instance
            branch = self.active_branch

            if branch == self.github_base_branch:
                return (
                    f"You're attempting to commit directly to the {self.github_base_branch} branch, "
                    "which is protected. Please create a new branch and try again."
                )

            try:
                file = repo.get_contents(file_path, ref=branch)
                if file:
                    return f"File {file_path} already exists. Use update_file instead."
            except Exception:
                # expected behavior, file shouldn't exist yet
                pass

            repo.create_file(
                path=file_path,
                message=f"Create {file_path}",
                content=file_contents,
                branch=branch,
            )
            return f"Created file {file_path}"
        except Exception as e:
            return f"Unable to create file due to error:\n{str(e)}"

    def extract_old_new_pairs(self, file_query):
        # Split the file content by lines
        code_lines = file_query.split("\n")

        # Initialize lists to hold the contents of OLD and NEW sections
        old_contents = []
        new_contents = []

        # Initialize variables to track whether the current line is within an OLD or NEW section
        in_old_section = False
        in_new_section = False

        # Temporary storage for the current section's content
        current_section_content = []

        # Iterate through each line in the file content
        for line in code_lines:
            # Check for OLD section start
            if "OLD <<<" in line:
                in_old_section = True
                current_section_content = []  # Reset current section content
                continue  # Skip the line with the marker

            # Check for OLD section end
            if ">>>> OLD" in line:
                in_old_section = False
                old_contents.append("\n".join(current_section_content).strip())  # Add the captured content
                current_section_content = []  # Reset current section content
                continue  # Skip the line with the marker

            # Check for NEW section start
            if "NEW <<<" in line:
                in_new_section = True
                current_section_content = []  # Reset current section content
                continue  # Skip the line with the marker

            # Check for NEW section end
            if ">>>> NEW" in line:
                in_new_section = False
                new_contents.append("\n".join(current_section_content).strip())  # Add the captured content
                current_section_content = []  # Reset current section content
                continue  # Skip the line with the marker

            # If currently in an OLD or NEW section, add the line to the current section content
            if in_old_section or in_new_section:
                current_section_content.append(line)

        # Pair the OLD and NEW contents
        paired_contents = list(zip(old_contents, new_contents))

        return paired_contents

    def update_file(self, file_query: str, repo_name: Optional[str] = None, commit_message: Optional[str] = None) -> str:
        """
        Updates a file with new content.
        Parameters:
            file_query(str): Contains the file path and the file contents.
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
            repo_name (Optional[str]): Name of the repository in format 'owner/repo'

        Returns:
            A success or failure message
        """
        try:
            repo = self.github_api.get_repo(repo_name) if repo_name else self.github_repo_instance
            branch = self.active_branch

            if branch == self.github_base_branch:
                return (
                    f"You're attempting to commit directly to the {self.github_base_branch} branch, "
                    "which is protected. Please create a new branch and try again."
                )

            file_path: str = file_query.split("\n")[0]

            file_content = self._read_file(file_path, branch, repo_name)
            updated_file_content = file_content
            for old, new in self.extract_old_new_pairs(file_query):
                if not old.strip():
                    continue
                updated_file_content = updated_file_content.replace(old, new)

            if file_content == updated_file_content:
                return (
                    "File content was not updated because old content was not found or empty. "
                    "It may be helpful to use the read_file action to get the current file contents."
                )

            repo.update_file(
                path=file_path,
                message=commit_message if commit_message else f"Update {file_path}",
                content=updated_file_content,
                branch=branch,
                sha=repo.get_contents(file_path, ref=branch).sha,
            )
            return f"Updated file {file_path}"
        except Exception as e:
            return f"Unable to update file due to error:\n{str(e)}"

    def delete_file(self, file_path: str, repo_name: Optional[str] = None) -> str:
        """
        Deletes a file from the repository.

        Parameters:
            file_path (str): The path of the file to delete
            repo_name (Optional[str]): Name of the repository in format 'owner/repo'

        Returns:
            str: A success or failure message
        """
        try:
            repo = self.github_api.get_repo(repo_name) if repo_name else self.github_repo_instance
            branch = self.active_branch

            if branch == self.github_base_branch:
                return (
                    f"You're attempting to commit directly to the {self.github_base_branch} branch, "
                    "which is protected. Please create a new branch and try again."
                )

            try:
                file = repo.get_contents(file_path, ref=branch)
                if not file:
                    return f"File {file_path} not found."
            except Exception as e:
                return f"File {file_path} not found. Error: {str(e)}"

            repo.delete_file(
                path=file_path,
                message=f"Delete {file_path}",
                sha=file.sha,
                branch=branch,
            )
            return f"Deleted file {file_path}"
        except Exception as e:
            return f"Unable to delete file due to error:\n{str(e)}"

    def validate_search_query(self, query: str) -> bool:
        """
        Validates a search query against expected GitHub search syntax using regular expressions.

        Parameters:
            query (str): The search query to validate.

        Returns:
            bool: True if valid, False otherwise.
        """
        # GitHub search supports complex queries with multiple filters, so we need a more permissive check
        # This pattern allows for common GitHub search syntax including filters, values with dots, etc.
        # We're mainly checking that the query isn't empty and doesn't contain dangerous characters
        if not query or not query.strip():
            return False

        # Check for potentially dangerous inputs (basic validation)
        dangerous_patterns = [
            r'<script', r'javascript:', r'onerror=', r'onclick=',
            r'data:text/html', r'alert\(', r'eval\('
        ]
        return not any(re.search(pattern, query, re.IGNORECASE) for pattern in dangerous_patterns)

    def search_issues(self, search_query: str, repo_name: Optional[str] = None, max_count: int = 30) -> str:
        """
        Searches for issues in a specific repository or a default initialized repository
        based on a search query using GitHub's search feature.

        Parameters:
            search_query (str): Keywords or query for searching issues and PRs in Github (supports GitHub search syntax).
            repo_name (Optional[str]): Name of the repository to search issues in. If None, use the initialized repository.
            max_count (int): Default is 30. This determines max size of returned list with issues

        Returns:
            str: JSON string containing a list of issues and PRs with their details (id, title, description, status, URL, type)
        """
        try:
            # Handle case when parameters are passed as a dictionary (from kwargs)
            if isinstance(search_query, dict):
                kwargs = search_query
                search_query = kwargs.get('search_query', '')
                repo_name = kwargs.get('repo_name', repo_name)
                max_count = kwargs.get('max_count', max_count)

            if not isinstance(search_query, str):
                return "Invalid search query. Search query must be a string."

            if not self.validate_search_query(search_query):
                return "Invalid search query. Please ensure it matches expected GitHub search syntax."

            target_repo = self.github_repo_instance.full_name if repo_name is None else repo_name

            query = f"repo:{target_repo} {search_query}"
            search_result = self.github_api.search_issues(query)

            if not search_result.totalCount:
                return "No issues or PRs found matching your query."

            matching_issues = []

            count = min(max_count, search_result.totalCount)
            for issue in search_result[:count]:
                issue_details = {
                    "id": issue.number,
                    "title": issue.title,
                    "description": issue.body,
                    "status": issue.state,
                    "url": issue.html_url,
                    "type": "PR" if issue.pull_request else "Issue"
                }
                matching_issues.append(issue_details)

            return matching_issues
        except Exception as e:
            return f"An error occurred while searching issues:\n{str(e)}"

    def create_issue(self, title: str, body: Optional[str] = None, repo_name: Optional[str] = None,
                     labels: Optional[List[str]] = None, assignees: Optional[List[str]] = None) -> str:
        """
        Creates a new issue in the GitHub repository.

        Parameters:
            title (str): The title of the issue.
            body (Optional[str]): The detailed description of the issue.
            repo_name (Optional[str]): Name of the repository in format 'owner/repo'
            labels (Optional[List[str]]): An optional list of labels to attach to the issue.
            assignees (Optional[List[str]]): An optional list of GitHub usernames to assign the issue to.

        Returns:
            str: A success or failure message along with the URL to the newly created issue.
        """
        try:
            repo = self.github_api.get_repo(repo_name) if repo_name else self.github_repo_instance

            if not repo:
                return "GitHub repository instance is not found or not initialized."

            issue = repo.create_issue(
                title=title,
                body=body,
                labels=labels if labels else [],
                assignees=assignees if assignees else []
            )

            return f"Issue created successfully! ID:{issue.number}, URL: {issue.html_url}"
        except Exception as e:
            return f"An error occurred while creating the issue: {str(e)}"

    def update_issue(self, issue_id: int, title: Optional[str] = None,
                     body: Optional[str] = None, labels: Optional[List[str]] = None,
                     assignees: Optional[List[str]] = None, state: Optional[str] = None,
                     repo_name: Optional[str] = None) -> str:
        """
        Updates an existing issue in a specified GitHub repository.

        Parameters:
            issue_id (int): ID of the issue to update.
            title (str): New title of the issue, if updating.
            body (Optional[str]): New detailed description of the issue, if updating.
            labels (Optional[List[str]]): New list of labels to apply to the issue, if updating.
            assignees (Optional[List[str]]): New list of GitHub usernames to assign to the issue, if updating.
            state (Optional[str]): New state of the issue ("open" or "closed"), if updating.
            repo_name (Optional[str]): Name of the repository where the issue exists.

        Returns:
            str: A confirmation message including the updated issue details, or an error message.
        """
        if not issue_id:
            return "Issue ID is required."
        try:
            repo = self.github_api.get_repo(repo_name) if repo_name else self.github_repo_instance
            issue = repo.get_issue(number=issue_id)

            if not issue:
                return f"Issue with #{issue_id} has not been found."

            if labels is None or labels == []:
                current_labels = [label.name for label in issue.get_labels()]
                for label in current_labels:
                    issue.remove_from_labels(label)

            if not assignees:
                for assignee in issue.assignees:
                    issue.remove_from_assignees(assignee)

            update_fields = {}
            if title:
                update_fields["title"] = title
            if body:
                update_fields["body"] = body
            if labels:
                update_fields["labels"] = labels
            if assignees:
                update_fields["assignees"] = assignees
            if state:
                update_fields["state"] = state

            issue.edit(**update_fields)

            return f"Issue updated successfully! Updated details: ID: {issue.number}, URL: {issue.html_url}"
        except Exception as e:
            return f"An error occurred while updating the issue: {str(e)}"

    def _file_commit_hash(self, file_path: str, branch: str, repo_name: Optional[str] = None) -> str:
        """
        Get the commit hash of a file in a specific branch.
        Parameters:
            file_path(str): the file path
            branch(str): the branch to read the file from
            repo_name (Optional[str]): Name of the repository in format 'owner/repo'

        Returns:
            str: The commit hash of the file, or an error message if not found
        """
        try:
            repo = self.github_api.get_repo(repo_name) if repo_name else self.github_repo_instance
            file = repo.get_contents(file_path, ref=branch)
            return file.sha
        except Exception as e:
            return f"File not found `{file_path}` on branch `{branch}`. Error: {str(e)}"

    def _read_file(self, file_path: str, branch: str, repo_name: Optional[str] = None) -> str:
        """
        Read a file from specified branch
        Parameters:
            file_path(str): the file path
            branch(str): the branch to read the file from
            repo_name (Optional[str]): Name of the repository in format 'owner/repo'

        Returns:
            str: The file decoded as a string, or an error message if not found
        """
        try:
            repo = self.github_api.get_repo(repo_name) if repo_name else self.github_repo_instance
            file = repo.get_contents(file_path, ref=branch)
            return file.decoded_content.decode("utf-8")
        except Exception as e:
            from traceback import format_exc
            return f"File not found `{file_path}` on branch `{branch}`. Error: {str(e)}"

    def read_file(self, file_path: str, branch: Optional[str] = None, repo_name: Optional[str] = None) -> str:
        """
        Read a file from the active branch
        Parameters:
            file_path(str): the file path
            branch (Optional[str]): The branch to read the file from. Defaults to the active branch.
            repo_name (Optional[str]): Name of the repository in format 'owner/repo'

        Returns:
            str: The file contents as a string
        """
        return self._read_file(file_path, branch if branch else self.active_branch, repo_name)

    def loader(self,
               branch: Optional[str] = None,
               whitelist: Optional[List[str]] = None,
               blacklist: Optional[List[str]] = None,
               repo_name: Optional[str] = None) -> str:
        """
        Generates file content from a branch, respecting whitelist and blacklist patterns.

        Parameters:
            branch (Optional[str]): Branch for listing files. Defaults to the current branch if None.
            whitelist (Optional[List[str]]): File extensions or paths to include. Defaults to all files if None.
            blacklist (Optional[List[str]]): File extensions or paths to exclude. Defaults to no exclusions if None.
            repo_name (Optional[str]): Name of the repository in format 'owner/repo'

        Returns:
            str: Parsed file content as JSON

        Example:
            # Use 'feature-branch', include '.py' files, exclude 'test_' files
            file_generator = loader(branch='feature-branch', whitelist=['*.py'], blacklist=['*test_*'])

        Notes:
            - Whitelist and blacklist use Unix shell-style wildcards.
            - Files must match the whitelist and not the blacklist to be included.
        """
        _files = self._get_files("", branch or self.active_branch, repo_name)

        def is_whitelisted(file_path: str) -> bool:
            if whitelist:
                return any(fnmatch.fnmatch(file_path, pattern) for pattern in whitelist)
            return True

        def is_blacklisted(file_path: str) -> bool:
            if blacklist:
                return any(fnmatch.fnmatch(file_path, pattern) for pattern in blacklist)
            return False

        def file_content_generator():
            for file in _files:
                if is_whitelisted(file) and not is_blacklisted(file):
                    yield {"file_name": file,
                           "file_content": self._read_file(file, branch=branch or self.active_branch, repo_name=repo_name)}

        try:
            from ..chunkers.code.codeparser import parse_code_files_for_db
            return parse_code_files_for_db(file_content_generator())
        except ImportError as e:
            return f"Error processing code files: {str(e)}"

    def list_branches_in_repo(self, repo_name: Optional[str] = None) -> str:
        """
        Lists all branches in the repository.

        Parameters:
            repo_name (Optional[str]): Name of the repository in format 'owner/repo'

        Returns:
            str: JSON string containing a list of branches
        """
        try:
            repo = self.github_api.get_repo(repo_name) if repo_name else self.github_repo_instance
            branches = repo.get_branches()
            branch_list = [{"name": branch.name, "protected": branch.protected} for branch in branches]
            return branch_list
        except Exception as e:
            return f"Failed to list branches: {str(e)}"

    def set_active_branch(self, branch_name: str, repo_name: Optional[str] = None) -> str:
        """
        Sets the active branch for future operations.

        Parameters:
            branch_name (str): Name of the branch to set as active
            repo_name (Optional[str]): Name of the repository in format 'owner/repo'

        Returns:
            str: Success message or error
        """
        try:
            # If repo_name is provided, we can't change the active branch for other repositories
            if repo_name:
                return (
                    "Cannot set active branch for external repository. "
                    "The active branch setting only applies to the default repository."
                )

            # Check if the branch exists
            repo = self.github_repo_instance
            try:
                repo.get_branch(branch_name)
                self.active_branch = branch_name
                return f"Active branch set to '{branch_name}'"
            except Exception:
                return f"Branch '{branch_name}' not found in repository"
        except Exception as e:
            return f"Failed to set active branch: {str(e)}"

    def trigger_workflow(self, workflow_id: str, ref: str, inputs: Optional[Dict[str, Any]] = None, repo_name: Optional[str] = None) -> str:
        """
        Triggers a GitHub Actions workflow run manually.

        Parameters:
            workflow_id (str): The ID or file name of the workflow to trigger (e.g., 'build.yml', '1234567')
            ref (str): The branch or tag reference to trigger the workflow on (e.g., 'main', 'v1.0.0')
            inputs (Optional[Dict[str, Any]]): Optional inputs for the workflow, as defined in the workflow file
            repo_name (Optional[str]): Name of the repository in format 'owner/repo'

        Returns:
            str: A JSON string containing the workflow run details, including the run ID
        """
        try:
            repo = self.github_api.get_repo(repo_name) if repo_name else self.github_repo_instance

            # First try to get the workflow by its filename
            try:
                workflow = repo.get_workflow(workflow_id)
            except Exception:
                # If that fails, try by ID
                try:
                    workflows = repo.get_workflows()
                    workflow = next(wf for wf in workflows if str(wf.id) == workflow_id)
                except StopIteration:
                    return f"Workflow with ID or filename '{workflow_id}' not found in repository {repo.full_name}"

            # Create a workflow dispatch event
            workflow_run = workflow.create_dispatch(ref, inputs or {})

            # Return run details
            result = {
                "success": True,
                "message": f"Workflow '{workflow.name}' triggered successfully on ref '{ref}'",
                "workflow_id": workflow.id,
                "workflow_name": workflow.name,
                "workflow_url": workflow.html_url,
                "ref": ref,
                "inputs": inputs or {}
            }

            return result
        except Exception as e:
            return f"An error occurred while triggering workflow: {str(e)}"

    def get_workflow_status(self, run_id: str, repo_name: Optional[str] = None) -> str:
        """
        Gets the status and details of a specific GitHub Actions workflow run.

        Parameters:
            run_id (str): The ID of the workflow run to get status for
            repo_name (Optional[str]): Name of the repository to get workflow status from

        Returns:
            str: A JSON string containing details about the workflow run status
        """
        try:
            repo = self.github_api.get_repo(repo_name) if repo_name else self.github_repo_instance

            # Get the workflow run
            run = repo.get_workflow_run(int(run_id))

            # Get additional details about the run jobs
            jobs = list(run.jobs())
            job_details = []

            for job in jobs:
                job_details.append({
                    "id": job.id,
                    "name": job.name,
                    "status": job.status,
                    "conclusion": job.conclusion,
                    "started_at": job.started_at.isoformat() if job.started_at else None,
                    "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                    "url": job.html_url
                })

            # Compile the results
            result = {
                "id": run.id,
                "name": run.name,
                "workflow_id": run.workflow_id,
                "event": run.event,
                "status": run.status,
                "conclusion": run.conclusion,
                "created_at": run.created_at.isoformat() if run.created_at else None,
                "updated_at": run.updated_at.isoformat() if run.updated_at else None,
                "head_branch": run.head_branch,
                "head_sha": run.head_sha,
                "jobs": job_details,
                "url": run.html_url
            }

            return result
        except Exception as e:
            # Return error as JSON instead of plain text
            return {
                "error": True,
                "message": f"An error occurred while getting workflow status: {str(e)}"
            }

    def get_workflow_logs(self, run_id: str, repo_name: Optional[str] = None) -> str:
        """
        Gets the logs from a GitHub Actions workflow run.

        Parameters:
            run_id (str): The ID of the workflow run to get logs for
            repo_name (Optional[str]): Name of the repository to get workflow logs from

        Returns:
            str: A JSON string containing logs from the workflow run's jobs
        """
        try:
            repo = self.github_api.get_repo(repo_name) if repo_name else self.github_repo_instance

            # Get the workflow run
            run = repo.get_workflow_run(int(run_id))

            # Get the run's logs
            try:
                # First approach: Try to get logs from the API directly if possible
                log_url = run.logs_url
                logs_zip = run.get_logs()  # This will give us a bytes object with the ZIP content

                import zipfile
                from io import BytesIO

                log_contents = {}
                with zipfile.ZipFile(BytesIO(logs_zip)) as zip_file:
                    for file_name in zip_file.namelist():
                        with zip_file.open(file_name) as log_file:
                            log_contents[file_name] = log_file.read().decode('utf-8', errors='replace')

                # Return the extracted logs
                return {
                    "run_id": run.id,
                    "status": run.status,
                    "conclusion": run.conclusion,
                    "logs": log_contents
                }
            except Exception as e:
                # Fallback approach: Get logs from individual jobs
                jobs = list(run.jobs())
                job_logs = []

                for job in jobs:
                    job_logs.append({
                        "job_id": job.id,
                        "job_name": job.name,
                        "status": job.status,
                        "conclusion": job.conclusion,
                        "steps": [
                            {
                                "name": step.name,
                                "status": step.status,
                                "conclusion": step.conclusion,
                                "number": step.number,
                                "started_at": step.started_at.isoformat() if step.started_at else None,
                                "completed_at": step.completed_at.isoformat() if step.completed_at else None
                            } for step in job.steps
                        ],
                        "logs_url": job.logs_url if hasattr(job, 'logs_url') else "No direct logs URL available"
                    })

                return {
                    "run_id": run.id,
                    "status": run.status,
                    "conclusion": run.conclusion,
                    "job_details": job_logs,
                    "note": "Full logs couldn't be retrieved directly. Only job details are available."
                }
        except Exception as e:
            return f"An error occurred while getting workflow logs: {str(e)}"

    def comment_on_issue(self, issue_number: str, comment: str, repo_name: Optional[str] = None) -> str:
        """
        Adds a comment to an issue or pull request

        Parameters:
            issue_number (str): The issue or PR number to comment on
            comment (str): The text of the comment to add
            repo_name (Optional[str]): Name of the repository in format 'owner/repo'

        Returns:
            str: Success message with URL to the comment
        """
        try:
            repo = self.github_api.get_repo(repo_name) if repo_name else self.github_repo_instance
            issue = repo.get_issue(int(issue_number))
            new_comment = issue.create_comment(comment)

            return f"Comment added successfully! URL: {new_comment.html_url}"
        except Exception as e:
            return f"Failed to add comment: {str(e)}"

    def create_pull_request(self, title: str, body: str, head: Optional[str] = None,
                           base: Optional[str] = None, repo_name: Optional[str] = None) -> str:
        """
        Creates a new pull request

        Parameters:
            title (str): Title of the PR
            body (str): Description of the PR
            head (Optional[str]): The branch containing the changes (defaults to active_branch)
            base (Optional[str]): The target branch (defaults to github_base_branch)
            repo_name (Optional[str]): Name of the repository in format 'owner/repo'

        Returns:
            str: Success message with PR URL and number
        """
        try:
            repo = self.github_api.get_repo(repo_name) if repo_name else self.github_repo_instance
            head_branch = head if head else self.active_branch
            base_branch = base if base else self.github_base_branch

            pr = repo.create_pull(
                title=title,
                body=body,
                head=head_branch,
                base=base_branch
            )

            return f"Pull request created successfully! PR #{pr.number}, URL: {pr.html_url}"
        except Exception as e:
            return f"Failed to create pull request: {str(e)}"

    def get_issues(self, state: str = "open", repo_name: Optional[str] = None) -> str:
        """
        Get a list of issues from the repository

        Parameters:
            state (str): Filter by state ("open", "closed", or "all")
            repo_name (Optional[str]): Name of the repository in format 'owner/repo'

        Returns:
            str: JSON string with issue data
        """
        try:
            repo = self.github_api.get_repo(repo_name) if repo_name else self.github_repo_instance
            issues = repo.get_issues(state=state)

            issue_list = [
                {
                    "number": issue.number,
                    "title": issue.title,
                    "state": issue.state,
                    "created_at": issue.created_at.isoformat(),
                    "updated_at": issue.updated_at.isoformat(),
                    "url": issue.html_url,
                    "labels": [label.name for label in issue.labels],
                    "assignees": [assignee.login for assignee in issue.assignees]
                }
                for issue in issues
            ]

            return issue_list
        except Exception as e:
            return f"Failed to get issues: {str(e)}"

    def list_open_pull_requests(self, repo_name: Optional[str] = None) -> str:
        """
        Lists all open pull requests for a repository.

        Parameters:
            repo_name (Optional[str]): Name of the repository in format 'owner/repo'

        Returns:
            str: A JSON string containing a list of open pull requests and their details
        """
        try:
            repo = self.github_api.get_repo(repo_name) if repo_name else self.github_repo_instance
            open_prs = repo.get_pulls(state='open')

            pr_list = []
            for pr in open_prs:
                pr_data = {
                    "number": pr.number,
                    "title": pr.title,
                    "state": pr.state,
                    "created_at": pr.created_at.isoformat() if pr.created_at else None,
                    "updated_at": pr.updated_at.isoformat() if pr.updated_at else None,
                    "html_url": pr.html_url,
                    "user": pr.user.login if pr.user else None,
                    "head": pr.head.ref,
                    "base": pr.base.ref
                }
                pr_list.append(pr_data)

            return pr_list
        except Exception as e:
            return f"Failed to list open pull requests: {str(e)}"

    def generic_github_api_call(self, method: str, method_kwargs: Optional[Dict[str, Any]] = None) -> str:
        """
        Generic method to make API calls to GitHub.
        method will be the name of the method to call on the GitHub API (python library).
        method_kwargs will be the parameters to pass to that method.

        Parameters:
            method (str): The API method to call (e.g., 'get_repo', 'get_user', etc.).
            method_kwargs (Optional[Dict[str, Any]]): Keyword arguments for the API method.

        Returns:
            JSON string with the response from the API call or an appropriate error message.
        """
        try:
            # Default `method_kwargs` to an empty dictionary if None is provided
            method_kwargs = method_kwargs or {}

            if method == "get_repo" and "full_name_or_id" not in method_kwargs:
                # You can customize the value based on your requirements
                method_kwargs["full_name_or_id"] = self.github_repository

            # Ensure `method` exists on the GitHub API or repository instance
            if hasattr(self.github_api, method):
                _method = getattr(self.github_api, method)
            elif self.github_repo_instance and hasattr(self.github_repo_instance, method):
                _method = getattr(self.github_repo_instance, method)
            else:
                return f"API method '{method}' not found on GitHub API or repository instance."

            # Call the method with the provided arguments
            response = _method(**method_kwargs)

            # Ensure `raw_data` exists in the response object
            if hasattr(response, "raw_data"):
                return response.raw_data
            else:
                return f"API method '{method}' was called successfully, but 'raw_data' attribute is missing in the response."

        except Exception as e:
            import traceback
            return f"API call failed: {traceback.format_exc()}"

    def get_available_tools(self) -> List[Dict[str, Any]]:
        return [
             {
                "ref": self.get_issues,
                "name": "get_issues",
                "mode": "get_issues",
                "description": GET_ISSUES_PROMPT,
                "args_schema": NoInput,
            },
            {
                "ref": self.get_issue,
                "name": "get_issue",
                "mode": "get_issue",
                "description": GET_ISSUE_PROMPT,
                "args_schema": GetIssue,
            },
            {
                "ref": self.comment_on_issue,
                "name": "comment_on_issue",
                "mode": "comment_on_issue",
                "description": COMMENT_ON_ISSUE_PROMPT,
                "args_schema": CommentOnIssue,
            },
            {
                "ref": self.list_open_pull_requests,
                "name": "list_open_pull_requests",
                "mode": "list_open_pull_requests",
                "description": LIST_PRS_PROMPT,
                "args_schema": NoInput,
            },
            {
                "ref": self.get_pull_request,
                "name": "get_pull_request",
                "mode": "get_pull_request",
                "description": GET_PR_PROMPT,
                "args_schema": GetPR,
            },
            {
                "ref": self.list_pull_request_diffs,
                "name": "list_pull_request_diffs",
                "mode": "list_pull_request_diffs",
                "description": LIST_PULL_REQUEST_FILES,
                "args_schema": GetPR, # Uses repo_name, pr_number
            },
            {
                "ref": self.create_pull_request,
                "name": "create_pull_request",
                "mode": "create_pull_request",
                "description": CREATE_PULL_REQUEST_PROMPT,
                "args_schema": CreatePR,
            },
            {
                "ref": self.create_file,
                "name": "create_file",
                "mode": "create_file",
                "description": CREATE_FILE_PROMPT,
                "args_schema": CreateFile,
            },
            {
                "ref": self.read_file,
                "name": "read_file",
                "mode": "read_file",
                "description": READ_FILE_PROMPT,
                "args_schema": ReadFile,
            },
            {
                "ref": self.update_file,
                "name": "update_file",
                "mode": "update_file",
                "description": UPDATE_FILE_PROMPT,
                "args_schema": UpdateFile,
            },
            {
                "ref": self.delete_file,
                "name": "delete_file",
                "mode": "delete_file",
                "description": DELETE_FILE_PROMPT,
                "args_schema": DeleteFile,
            },
            {
                "ref": self.list_files_in_main_branch,
                "name": "list_files_in_main_branch",
                "mode": "list_files_in_main_branch",
                "description": OVERVIEW_EXISTING_FILES_IN_MAIN,
                "args_schema": NoInput,
            },
            {
                "ref": self.list_files_in_bot_branch,
                "name": "list_files_in_bot_branch",
                "mode": "list_files_in_bot_branch",
                "description": "Lists files in the bot's currently active working branch.",
                "args_schema": NoInput,
            },
            {
                "ref": self.list_branches_in_repo,
                "name": "list_branches_in_repo",
                "mode": "list_branches_in_repo",
                "description": LIST_BRANCHES_IN_REPO_PROMPT,
                "args_schema": NoInput,
            },
            {
                "ref": self.set_active_branch,
                "name": "set_active_branch",
                "mode": "set_active_branch",
                "description": SET_ACTIVE_BRANCH_PROMPT,
                "args_schema": BranchName,
            },
            {
                "ref": self.create_branch,
                "name": "create_branch",
                "mode": "create_branch",
                "description": CREATE_BRANCH_PROMPT,
                "args_schema": CreateBranchName,
            },
            {
                "ref": self.get_files_from_directory,
                "name": "get_files_from_directory",
                "mode": "get_files_from_directory",
                "description": GET_FILES_FROM_DIRECTORY_PROMPT,
                "args_schema": DirectoryPath,
            },
            {
                "ref": self.search_issues,
                "name": "search_issues",
                "mode": "search_issues",
                "description": SEARCH_ISSUES_AND_PRS_PROMPT,
                "args_schema": SearchIssues,
            },
            {
                "ref": self.create_issue,
                "name": "create_issue",
                "mode": "create_issue",
                "description": CREATE_ISSUE_PROMPT,
                "args_schema": CreateIssue,
            },
            {
                "ref": self.update_issue,
                "name": "update_issue",
                "mode": "update_issue",
                "description": UPDATE_ISSUE_PROMPT,
                "args_schema": UpdateIssue,
            },
            # {
            #     "ref": self.loader,
            #     "name": "loader",
            #     "mode": "loader",
            #     "description": self.loader.__doc__,
            #     "args_schema": LoaderSchema,
            # },
            {
                "ref": self.get_commits,
                "name": "get_commits",
                "mode": "get_commits",
                "description": self.get_commits.__doc__,
                "args_schema": GetCommits,
            },
            {
                "ref": self.get_commit_changes,
                "name": "get_commit_changes",
                "mode": "get_commit_changes",
                "description": self.get_commit_changes.__doc__,
                "args_schema": GetCommitChanges,
            },
            {
                "ref": self.get_commits_diff,
                "name": "get_commits_diff",
                "mode": "get_commits_diff",
                "description": self.get_commits_diff.__doc__,
                "args_schema": GetCommitsDiff,
            },
            {
                "ref": self.apply_git_patch,
                "name": "apply_git_patch",
                "mode": "apply_git_patch",
                "description": self.apply_git_patch.__doc__,
                "args_schema": ApplyGitPatch,
            },
            {
                "ref": self.apply_git_patch_from_file,
                "name": "apply_git_patch_from_file",
                "mode": "apply_git_patch_from_file",
                "description": self.apply_git_patch_from_file.__doc__,
                "args_schema": ApplyGitPatchFromArtifact,
            },
            {
                "ref": self.trigger_workflow,
                "name": "trigger_workflow",
                "mode": "trigger_workflow",
                "description": self.trigger_workflow.__doc__,
                "args_schema": TriggerWorkflow,
            },
            {
                "ref": self.get_workflow_status,
                "name": "get_workflow_status",
                "mode": "get_workflow_status",
                "description": self.get_workflow_status.__doc__,
                "args_schema": GetWorkflowStatus,
            },
            {
                "ref": self.get_workflow_logs,
                "name": "get_workflow_logs",
                "mode": "get_workflow_logs",
                "description": self.get_workflow_logs.__doc__,
                "args_schema": GetWorkflowLogs,
            },
            {
                "ref": self.generic_github_api_call,
                "name": "generic_github_api_call",
                "mode": "generic_github_api_call",
                "description": self.generic_github_api_call.__doc__,
                "args_schema": GenericGithubAPICall,
            },

        ]