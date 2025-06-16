### Guide for GitHub OAuth App

- Create a new OAuth App: 
GitHub > Settings > Developer Settings > OAuth Apps \
https://github.com/settings/developers

- Install `gh` on your local machine
MacOS:
```bash
brew install gh
```

- Log in GitHub using `project` scope:
MacOS:
```bash
gh auth login --scopes "project"
```

- Get auth token:
MacOS:
```bash
gh auth token
```

### Usage

#### Create issue on project

> VERY IMPORTANT: This method CANNOT be used with Personal token but with OAuth token having project scope only
> "X-Accepted-OAuth-Scopes" should include "project:admin"


src/alita_tools/github/api_wrapper.py::create_issue_on_project
\
```python
from src.alita_tools.github import AlitaGitHubAPIWrapper
from pydantic import ValidationError

try:
    api = AlitaGitHubAPIWrapper(
        github="https://github.com",
        github_repository="<owner_name>/<repository_name>",
        github_base_branch="master",
        active_branch="master",
        github_access_token="<oauth_app_token_with_project_scope>"
    )
except ValidationError as err:
    print(err.json(indent=4))

board_repo = "<org_name>/<repo_name>" # board repo
project_title = "<project_title>" # board title
issue_title = "Test Issue Title"
issue_description = "Test Description"
desired_fields = {
    "Environment": "Staging",
    "SR Type": "Issue/Bug Report",
    "SR Priority": "Medium",
    "Labels": ["bug", "documentation"],
    "Assignees": ["<assignee_name>"]
}

data = api.create_issue_on_project(board_repo, project_title, issue_title, issue_description, desired_fields)
print(f"\n> Result: {data}\n")
```

#### Update issue on project
> VERY IMPORTANT: This method CANNOT be used with Personal token but with OAuth token having project scope only
> "X-Accepted-OAuth-Scopes" should include "project:admin"


src/alita_tools/github/api_wrapper.py::update_issue_on_project
\
```python
from src.alita_tools.github import AlitaGitHubAPIWrapper
from pydantic import ValidationError

try:
    api = AlitaGitHubAPIWrapper(
        github="https://github.com",
        github_repository="<owner_name>/<repository_name>",
        github_base_branch="master",
        active_branch="master",
        github_access_token="<oauth_app_token_with_project_scope>"
    )
except ValidationError as err:
    print(err.json(indent=4))

board_repo = "<org_name>/<repo_name>" # board repo
project_title = "<project_title>" # board title
issue_number = "2"
issue_title = "New Test Issue Title"
issue_description = "New Test Description"
desired_fields = {
    "Environment": "All",
    "SR Type": "", # field will be removed
    "SR Priority": "High",
    "Labels": ["enchancement"],
    "Assignees": [] # all assignees will be removed
}

data = api.update_issue_on_project(board_repo, issue_number, project_title, issue_title, issue_description, desired_fields)
print(f"\n> Result: {data}\n")
```