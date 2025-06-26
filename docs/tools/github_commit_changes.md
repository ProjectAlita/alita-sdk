# GitHub Commit Changes Tool

## Overview

The `get_commit_changes` tool allows you to retrieve detailed information about files changed in a specific GitHub commit. This tool is part of the Alita SDK GitHub toolkit.

## Features

- Get a list of all files changed in a specific commit
- View file status (added, modified, removed, renamed)
- See addition and deletion counts for each file
- Access patch/diff information
- Get URLs for viewing files (blob_url, raw_url)
- Handle renamed files with previous filename information

## Usage

### Parameters

- `sha` (required): The commit SHA to get changed files for
- `repo_name` (optional): Repository name in format 'owner/repo'. If not provided, uses the default repository.

### Example Usage

```python
from alita_sdk.tools.github import AlitaGitHubAPIWrapper

# Initialize the wrapper
github_wrapper = AlitaGitHubAPIWrapper(
    github_access_token="your_token",
    github_repository="owner/repo"
)

# Get changes for a specific commit
result = github_wrapper.run("get_commit_changes", sha="abc123def456")

# Or specify a different repository
result = github_wrapper.run("get_commit_changes", 
                           sha="abc123def456", 
                           repo_name="other-owner/other-repo")
```

### Response Structure

The tool returns a dictionary containing:

```json
{
    "commit_sha": "abc123def456",
    "commit_message": "Fix bug in user authentication",
    "author": "John Doe",
    "date": "2025-06-25T10:30:00Z",
    "total_files_changed": 3,
    "total_additions": 25,
    "total_deletions": 8,
    "files": [
        {
            "filename": "src/auth.py",
            "status": "modified",
            "additions": 15,
            "deletions": 5,
            "changes": 20,
            "patch": "@@ -10,7 +10,7 @@ def authenticate(user):\n...",
            "blob_url": "https://github.com/owner/repo/blob/abc123/src/auth.py",
            "raw_url": "https://github.com/owner/repo/raw/abc123/src/auth.py"
        },
        {
            "filename": "tests/test_auth.py",
            "status": "added",
            "additions": 10,
            "deletions": 0,
            "changes": 10,
            "patch": "@@ -0,0 +1,10 @@\n+import unittest\n...",
            "blob_url": "https://github.com/owner/repo/blob/abc123/tests/test_auth.py",
            "raw_url": "https://github.com/owner/repo/raw/abc123/tests/test_auth.py"
        },
        {
            "filename": "config/new_config.yaml",
            "status": "renamed",
            "previous_filename": "config/old_config.yaml",
            "additions": 0,
            "deletions": 3,
            "changes": 3,
            "patch": "@@ -1,3 +1,0 @@\n-old_setting: value\n...",
            "blob_url": "https://github.com/owner/repo/blob/abc123/config/new_config.yaml",
            "raw_url": "https://github.com/owner/repo/raw/abc123/config/new_config.yaml"
        }
    ]
}
```

### File Status Values

- `added`: New file created in this commit
- `modified`: Existing file was changed
- `removed`: File was deleted in this commit
- `renamed`: File was moved/renamed (includes `previous_filename` field)

### Error Handling

If an error occurs, the tool returns:

```json
{
    "error": "Repository not found",
    "message": "Unable to retrieve commit changes due to error: Repository not found"
}
```

## Use Cases

1. **Code Review**: Analyze what files were changed in a specific commit
2. **Impact Analysis**: Understand the scope of changes in a commit
3. **Debugging**: Track file modifications when investigating issues
4. **Documentation**: Generate change logs based on commit file changes
5. **Automation**: Build workflows that react to specific file changes

## Requirements

- GitHub access token with appropriate repository permissions
- PyGithub library (automatically installed with Alita SDK)
- Internet connection to access GitHub API

## Related Tools

- `get_commits`: List commits in a repository
- `get_pull_request`: Get pull request information
- `read_file`: Read file contents from repository
- `search_issues`: Search for issues and pull requests
