# GitHub Commits History Tool

## Overview

The `get_commits` tool allows you to retrieve commit history from a GitHub repository with various filtering options including time periods, author filtering, file path filtering, and commit count limits.

## Parameters

- `sha` (optional): The commit SHA or branch name to start listing commits from
- `path` (optional): Filter commits that touched a specific file path  
- `since` (optional): Only commits after this date (ISO format) will be returned
- `until` (optional): Only commits before this date (ISO format) will be returned
- `author` (optional): Filter commits by author name
- `repo_name` (optional): Repository name in format 'owner/repo' (uses default if not specified)
- `max_count` (optional): Maximum number of commits to return (default: 30)

## Usage Examples

### 1. Get Recent Commits (Limited Count)
```python
# Get the last 10 commits
result = github_wrapper.run("get_commits", max_count=10)

# Get the last 50 commits  
result = github_wrapper.run("get_commits", max_count=50)
```

### 2. Get Commits by Time Period
```python
# Get commits from the last week
result = github_wrapper.run("get_commits", 
                           since="2025-06-18T00:00:00",
                           max_count=100)

# Get commits between specific dates
result = github_wrapper.run("get_commits",
                           since="2025-06-01T00:00:00",
                           until="2025-06-25T23:59:59")

# Get commits from the last month
result = github_wrapper.run("get_commits",
                           since="2025-05-25T00:00:00")
```

### 3. Get Commits by Author
```python
# Get last 20 commits by specific author
result = github_wrapper.run("get_commits",
                           author="john.doe",
                           max_count=20)

# Get author's commits in the last week
result = github_wrapper.run("get_commits",
                           author="jane.smith",
                           since="2025-06-18T00:00:00")
```

### 4. Get Commits for Specific Files
```python
# Get commits that modified a specific file
result = github_wrapper.run("get_commits",
                           path="src/main.py",
                           max_count=25)

# Get commits for files in a directory  
result = github_wrapper.run("get_commits",
                           path="src/",
                           since="2025-06-01T00:00:00")
```

### 5. Combined Filters
```python
# Get commits by author for specific file in time range
result = github_wrapper.run("get_commits",
                           author="john.doe",
                           path="config/settings.json",
                           since="2025-06-01T00:00:00",
                           until="2025-06-25T00:00:00",
                           max_count=15)
```

### 6. Different Repository
```python
# Get commits from a different repository
result = github_wrapper.run("get_commits",
                           repo_name="owner/other-repo",
                           max_count=20)
```

## Response Format

The tool returns a list of commit objects with the following structure:

```json
[
    {
        "sha": "abc123def456",
        "author": "John Doe", 
        "date": "2025-06-25T10:30:00Z",
        "message": "Fix authentication bug",
        "url": "https://github.com/owner/repo/commit/abc123def456"
    },
    {
        "sha": "def456ghi789",
        "author": "Jane Smith",
        "date": "2025-06-24T15:45:00Z", 
        "message": "Add new feature for user management",
        "url": "https://github.com/owner/repo/commit/def456ghi789"
    }
]
```

## Date Format

When using `since` and `until` parameters, use ISO 8601 format:
- `YYYY-MM-DDTHH:MM:SS` (e.g., `2025-06-25T10:30:00`)
- `YYYY-MM-DD` (e.g., `2025-06-25`) - defaults to midnight

## Common Use Cases

### 1. Daily Standup Reports
```python
# Get yesterday's commits for team review
result = github_wrapper.run("get_commits",
                           since="2025-06-24T00:00:00",
                           until="2025-06-24T23:59:59")
```

### 2. Release Notes Generation
```python
# Get all commits since last release
result = github_wrapper.run("get_commits",
                           since="2025-06-01T00:00:00",
                           max_count=100)
```

### 3. Code Review Preparation  
```python
# Get commits by specific developer for review
result = github_wrapper.run("get_commits",
                           author="new.developer",
                           since="2025-06-20T00:00:00")
```

### 4. File Change Tracking
```python
# Track changes to critical configuration files
result = github_wrapper.run("get_commits",
                           path="config/production.yaml",
                           since="2025-06-01T00:00:00")
```

### 5. Performance Analysis
```python
# Limit results for faster queries
result = github_wrapper.run("get_commits", max_count=5)  # Just last 5 commits
```

## Error Handling

If an error occurs, the tool returns:
```json
{
    "error": "Repository not found",
    "message": "Unable to retrieve commits due to error: Repository not found"
}
```

## Related Tools

- `get_commit_changes`: Get detailed file changes for a specific commit
- `get_pull_request`: Get pull request information
- `search_issues`: Search for issues and pull requests
- `list_pull_request_diffs`: Get file changes in a pull request
