CREATE_FILE_PROMPT = """Create new file in your github repository."""

UPDATE_FILE_PROMPT = """Updates the contents of a file in repository. Input MUST strictly follow these rules:
Specify the file to modify by passing a full file path (the path must not start with a slash); Specify at lest 2 lines of the old contents which you would like to replace wrapped in OLD <<<< and >>>> OLD; Specify the new contents which you would like to replace the old contents with wrapped in NEW <<<< and >>>> NEW; NEW content may contain lines from OLD content in case you want to add content without removing the old content

Example 1: Replace "old contents" to "new contents" in the file /test/test.txt from , pass in the following string:

test/test.txt

This is text that will not be changed
OLD <<<<
old contents
>>>> OLD
NEW <<<<
new contents
>>>> NEW

Example 2: Extend "existing contents" with new contents" in the file /test/test.txt, pass in the following string:

test/test.txt

OLD <<<<
existing contents
>>>> OLD
NEW <<<<
existing contents
new contents
>>>> NEW"""

CREATE_ISSUE_PROMPT = """
Tool allows to create a new issue in a GitHub repository.
**IMPORTANT**: Input to this tool MUST strictly follow these rules:
- First, you must specify the title of the issue.
Optionally you can specify:
- a detailed description or body of the issue
- labels for the issue, each separated by a comma. For labels, write `labels:` followed by a comma-separated list of labels.
- assignees for the issue, each separated by a comma. For assignees, write `assignees:` followed by a comma-separated 
list of GitHub usernames.

Ensure that each command (`labels:` and `assignees:`) starts in a new line, if used.

For example, if you would like to create an issue titled "Fix login bug" with a body explaining the problem and tagged with `bug` 
and `urgent` labels, plus assigned to `user123`, you would pass in the following string:

Fix login bug

The login button isn't responding on the main page. Reproduced on various devices.

labels: bug, urgent
assignees: user123
"""

UPDATE_ISSUE_PROMPT = """
Tool allows you to update an existing issue in a GitHub repository. **IMPORTANT**: Input MUST follow 
these rules:
- You must specify the repository name where the issue exists.
- You must specify the issue ID that you wish to update.

Optional fields:
- You can then provide the new title of the issue.
- You can provide a new detailed description or body of the issue.
- You can specify new labels for the issue, each separated by a comma.
- You can specify new assignees for the issue, each separated by a comma.
- You can change the state of the issue to either 'open' or 'closed'.

If assignees or labels are not passed or passed as empty lists they will be removed from the issue.

For example, to update an issue in the 'octocat/Hello-World' repository with ID 42, changing the title and closing the issue, the input should be:

octocat/Hello-World

42

New Issue Title

New detailed description goes here.

labels: bug, ui

assignees: user1, user2

closed
"""

CREATE_ISSUE_ON_PROJECT_PROMPT = """
Tool allows for creating GitHub issues within specified projects. Adhere to these steps:

1. Specify both project and issue titles.
2. Optionally, include a detailed issue description and any additional required fields in JSON format.

Ensure JSON fields are correctly named as expected by the project.

**Example**:
For an issue titled "Fix Navigation Bar" in the "WebApp Redesign" project, addressing mobile view responsiveness, set as medium priority, in staging, and assigned to "dev_lead":

Project: WebApp Redesign
Issue Title: Fix Navigation Bar
Description: The navigation bar disappears on mobile view. Needs responsive fix.
JSON:
{
  "Environment": "Staging",
  "Priority": "Medium",
  "Labels": ["bug", "UI"],
  "Assignees": ["dev_lead"]
}
"""

UPDATE_ISSUE_ON_PROJECT_PROMPT = """
Tool updates GitHub issues for the specified project. Follow these steps:

- Provide the issue number and project title.
- Optionally, adjust the issue's title, description, and other fields.
- Use JSON key-value pairs to update or clear fields, setting empty strings to clear.

Ensure field names align with project requirements.

**Example**:
Update issue 42 in "WebApp Redesign," change its title, modify the description, and update settings:

Issue Number: 42
Project: WebApp Redesign
New Title: Update Navigation Bar

Description:
Implement dropdown menus based on user roles for full device compatibility.

JSON:
{
  "Environment": "Production",
  "Type": "Enhancement",
  "Priority": "High",
  "Labels": ["UI"],
  "Assignees": ["ui_team"]
}
"""

LIST_PROJECTS_ISSUES = """
Lists all issues in a GitHub project with their details including custom fields.

This method retrieves all issues in a project including their status, assignees,
custom fields, and other metadata.

Args:
    owner (str): Repository owner (organization or username).
    repo_name (str): Repository name.
    project_number (int): Project number (visible in project URL).
    items_count (int, optional): Maximum number of items to retrieve. Defaults to 100.
    
Returns:
    Union[Dict[str, Any], str]: Dictionary with project issues or error message.
    
Example:
    project_issues = client.list_project_issues(
        owner="octocat",
        repo_name="Hello-World",
        project_number=1
    )
"""

SEARCH_PROJECT_ISSUES = """
Searches for issues in a GitHub project matching specific criteria.

Args:
    board_repo: The organization and repository for the board (project).
    search_query: Search query for filtering issues. Can be a string or a dictionary of filter parameters.
    project_number: The project number as shown in the project URL.
    items_count: Maximum number of items to retrieve.
    repo_name: Optional repository name to override default.
    
Returns:
    str: JSON string with matching project issues including their metadata.
"""

LIST_PROJECT_VIEWS =  """
List views for a GitHub Project.

Args:
    board_repo: The organization and repository for the board (project).
    project_number: The project number (visible in the project URL).
    first: Number of views to fetch.
    after: Cursor for pagination.
    repo_name: Optional repository name to override default.
    
Returns:
    str: JSON string containing project views.
"""

GET_PROJECT_ITEMS_BY_VIEW = """
Get project items filtered by a specific project view.

Args:
    board_repo: The organization and repository for the board (project).
    project_number: The project number (visible in the project URL).
    view_number: The view number to filter by.
    first: Number of items to fetch.
    after: Cursor for pagination.
    filter_by: Dictionary containing filter parameters.
    repo_name: Optional repository name to override default.
    
Returns:
    str: JSON string containing project items.
"""

# GraphQL templates moved from graphql_github.py
from enum import Enum
from string import Template

class GraphQLTemplates(Enum):
    """
    Enum class to maintain consistent GraphQL query and mutation templates for GitHub operations.

    Attributes:
        QUERY_GET_PROJECT_INFO_TEMPLATE (Template): Template for a query to gather detailed info about projects and their contents
        in a specific repository including labels, assignable users, and project items.

        QUERY_GET_REPO_INFO_TEMPLATE (Template): Template for a query to get information about repository such as repository ID, labels, assignable users.
        
        QUERY_LIST_PROJECT_ISSUES (Template): Template for a query to list all issues in a project with their details.
        
        QUERY_LIST_PROJECT_ISSUES_PAGINATED (Template): Template for a query to list project issues with pagination support.
        
        QUERY_SEARCH_PROJECT_ISSUES (Template): Template for a query to search for issues in a project by title, status, or any field value.
        
        MUTATION_CREATE_DRAFT_ISSUE (Template): Template for a mutation to create a draft issue in a specific project.
        
        MUTATION_CONVERT_DRAFT_INTO_ISSUE (Template): Template for a mutation to convert a draft issue to a regular issue in a repository.
        
        MUTATION_UPDATE_ISSUE (Template): Template for a mutation to update the title and body of a specific issue.
        
        MUTATION_UPDATE_ISSUE_FIELDS (Template): Template for a mutation to update the field values of a project item.

        MUTATION_CLEAR_ISSUE_FIELDS (Template): Template for a mutation to clear the field values of a project item.
        
        MUTATION_SET_ISSUE_LABELS (Template): Template for a mutation to set labels to an issue.
        
        MUTATION_SET_ISSUE_ASSIGNEES (Template): Template for a mutation to add assignees to an issue.
        
        MUTATION_REMOVE_ISSUE_LABELS (Template): Template for a mutation to remove labels from an issue.
        
        MUTATION_REMOVE_ISSUE_ASSIGNEES (Template): Template for a mutation to remove assignees from an issue.
    """
    # bad design, it needs to be refactored to get information about project/repository separately 
    QUERY_GET_PROJECT_INFO_TEMPLATE = Template("""
    query {
        repository(owner: "$owner", name: "$repo_name") {
            id
            labels (first: 100) { nodes { id name } }
            assignableUsers (first: 100) { nodes { id name login } }
            projectsV2(first: 10) {
                nodes
                {
                    id
                    title
                    fields(first: 30) { 
                        nodes {
                            ... on ProjectV2SingleSelectField { 
                                id
                                dataType
                                name
                                options {
                                    id
                                    name
                                }
                            }
                            ... on ProjectV2FieldCommon { 
                                id
                                dataType
                                name
                            }
                        }
                    }
                    items(first: 100) {
                        nodes {
                            id
                            content {
                                ... on Issue {
                                    id
                                    number
                                    labels (first: 20) { nodes { id name } }
                                    assignees (first: 20) { nodes { id name } }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    """)

    QUERY_GET_REPO_INFO_TEMPLATE = Template("""
    query {
        repository(owner: "$owner", name: "$repo_name") {
            id
            labels (first: 100) { nodes { id name } }
            assignableUsers (first: 100) { nodes { id name login } }
        }
    }
    """)
    
    QUERY_LIST_PROJECT_ISSUES = Template("""
    query ProjectIssues($owner: String!, $repo_name: String!, $project_number: Int!, $items_count: Int = 100) {
        repository(owner: $owner, name: $repo_name) {
            projectV2(number: $project_number) {
                id
                title
                url
                fields(first: 30) {
                    nodes {
                        ... on ProjectV2SingleSelectField {
                            id
                            name
                            options {
                                id
                                name
                            }
                        }
                        ... on ProjectV2FieldCommon {
                            id
                            name
                            dataType
                        }
                    }
                }
                items(first: $items_count) {
                    nodes {
                        id
                        fieldValues(first: 30) {
                            nodes {
                                ... on ProjectV2ItemFieldTextValue {
                                    field { ... on ProjectV2FieldCommon { name } }
                                    text
                                }
                                ... on ProjectV2ItemFieldDateValue {
                                    field { ... on ProjectV2FieldCommon { name } }
                                    date
                                }
                                ... on ProjectV2ItemFieldSingleSelectValue {
                                    field { ... on ProjectV2FieldCommon { name } }
                                    name
                                    optionId
                                }
                            }
                        }
                        content {
                            ... on Issue {
                                id
                                number
                                title
                                state
                                body
                                url
                                createdAt
                                updatedAt
                                labels(first: 10) {
                                    nodes {
                                        id
                                        name
                                        color
                                    }
                                }
                                assignees(first: 5) {
                                    nodes {
                                        id
                                        login
                                        name
                                    }
                                }
                            }
                            ... on PullRequest {
                                id
                                number
                                title
                                state
                                body
                                url
                                createdAt
                                updatedAt
                            }
                            ... on DraftIssue {
                                id
                                title
                                body
                                createdAt
                            }
                        }
                    }
                }
            }
        }
    }
    """)

    QUERY_LIST_PROJECT_ISSUES_PAGINATED = Template("""
    query ProjectIssuesPaginated($owner: String!, $repo_name: String!, $project_number: Int!, $items_count: Int!, $after_cursor: String) {
        repository(owner: $owner, name: $repo_name) {
            projectV2(number: $project_number) {
                # No need to fetch fields again, assuming they were fetched initially
                items(first: $items_count, after: $after_cursor) {
                    nodes {
                        id
                        type # Added type
                        fieldValues(first: 30) {
                            nodes {
                                ... on ProjectV2ItemFieldTextValue {
                                    field { ... on ProjectV2FieldCommon { id name } } # Added ID
                                    text
                                }
                                ... on ProjectV2ItemFieldDateValue {
                                    field { ... on ProjectV2FieldCommon { id name } } # Added ID
                                    date
                                }
                                ... on ProjectV2ItemFieldSingleSelectValue {
                                    field { ... on ProjectV2FieldCommon { id name } } # Added ID
                                    name
                                    optionId # Keep optionId
                                    # Include option details if needed, e.g., for color
                                    # option { id name color } 
                                }
                                # Add other field value types as needed (Iteration, Number, etc.)
                            }
                        }
                        content {
                            ... on Issue {
                                id
                                number
                                title
                                state
                                url
                                createdAt
                                updatedAt
                                labels(first: 10) {
                                    nodes { id name color }
                                }
                                assignees(first: 5) {
                                    nodes { id login name }
                                }
                            }
                            ... on PullRequest {
                                id
                                number
                                title
                                state
                                url
                                createdAt
                                updatedAt
                            }
                            ... on DraftIssue {
                                id
                                title
                                createdAt
                                updatedAt
                            }
                        }
                    }
                    pageInfo {
                        endCursor
                        hasNextPage
                    }
                    totalCount # Keep totalCount if useful
                }
            }
        }
    }
    """)

    QUERY_SEARCH_PROJECT_ISSUES = Template("""
    query SearchProjectIssues($owner: String!, $repo_name: String!, $project_number: Int!, $items_count: Int = 100) {
        repository(owner: $owner, name: $repo_name) {
            projectV2(number: $project_number) {
                id
                title
                url
                fields(first: 30) {
                    nodes {
                        ... on ProjectV2SingleSelectField {
                            id
                            name
                            options {
                                id
                                name
                            }
                        }
                        ... on ProjectV2FieldCommon {
                            id
                            name
                            dataType
                        }
                    }
                }
                items(first: $items_count) {
                    nodes {
                        id
                        fieldValues(first: 30) {
                            nodes {
                                ... on ProjectV2ItemFieldTextValue {
                                    field { ... on ProjectV2FieldCommon { name } }
                                    text
                                }
                                ... on ProjectV2ItemFieldDateValue {
                                    field { ... on ProjectV2FieldCommon { name } }
                                    date
                                }
                                ... on ProjectV2ItemFieldSingleSelectValue {
                                    field { ... on ProjectV2FieldCommon { name } }
                                    name
                                    optionId
                                }
                            }
                        }
                        content {
                            ... on Issue {
                                id
                                number
                                title
                                state
                                body
                                url
                                createdAt
                                updatedAt
                                labels(first: 10) {
                                    nodes {
                                        id
                                        name
                                        color
                                    }
                                }
                                assignees(first: 5) {
                                    nodes {
                                        id
                                        login
                                        name
                                    }
                                }
                            }
                            ... on PullRequest {
                                id
                                number
                                title
                                state
                                body
                                url
                                createdAt
                                updatedAt
                            }
                            ... on DraftIssue {
                                id
                                title
                                body
                                createdAt
                            }
                        }
                    }
                }
            }
        }
    }
    """)

    MUTATION_CREATE_DRAFT_ISSUE = Template("""
    mutation ($projectId: ID!, $title: String!, $body: String!) {
    addProjectV2DraftIssue(input: {
        projectId: $projectId,
        title: $title,
        body: $body
    }) {
        projectItem {
            id
        }
    }
    }
    """)

    MUTATION_CONVERT_DRAFT_INTO_ISSUE = Template("""
    mutation ($draftItemId: ID!, $repositoryId: ID!) {
        convertProjectV2DraftIssueItemToIssue(input: {
            itemId: $draftItemId,
            repositoryId: $repositoryId
        }) {
            item {
                id
                content {
                    ... on Issue {
                        id
                        number
                    }
                }
            }
        }
    }
    """)

    MUTATION_UPDATE_ISSUE = Template("""
    mutation UpdateIssue($issueId: ID!, $title: String!, $body: String!) {
        updateIssue(input: {id: $issueId, title: $title, body: $body}) {
            issue {
                id
                number
                title
                body
            }
        }
    }
    """)

    MUTATION_UPDATE_ISSUE_FIELDS = Template("""
    mutation {
        updateProjectV2ItemFieldValue(input: 
        {
            projectId: "$project_id"
            itemId: "$issue_item_id",
            fieldId: "$field_id",
            value: {
                $value_content
            }
        }) {
            projectV2Item {
                id
                fieldValues(first: 30) {
                    nodes {
                        ... on ProjectV2ItemFieldSingleSelectValue {
                            id
                            name
                        }
                        ... on ProjectV2ItemFieldDateValue {
                            id
                            date
                        }
                        ... on ProjectV2ItemFieldLabelValue {
                            labels (first: 20) {
                                nodes { id name }
                            }
                        }                    
                    }
                }
            }
        }
    }
    """)

    MUTATION_CLEAR_ISSUE_FIELDS = Template("""
    mutation {
        clearProjectV2ItemFieldValue(input: 
        {
            projectId: "$project_id"
            itemId: "$issue_item_id",
            fieldId: "$field_id"
        }) {
            projectV2Item {
                id
                fieldValues(first: 30) {
                    nodes {
                        ... on ProjectV2ItemFieldSingleSelectValue {
                            id
                            name
                        }
                        ... on ProjectV2ItemFieldDateValue {
                            id
                            date
                        }
                        ... on ProjectV2ItemFieldLabelValue {
                            labels (first: 20) {
                                nodes { id name }
                            }
                        }
                    }
                }
            }
        }
    }
    """)

    MUTATION_SET_ISSUE_LABELS = Template("""
    mutation ($labelableId: ID!, $labelIds: [ID!]!) {
        addLabelsToLabelable(input: { labelableId: $labelableId, labelIds: $labelIds }) {
            labelable {
                ... on Issue {
                    labels (first: 100) { nodes { id name } }
                }
            }
        }
    }
    """)

    MUTATION_SET_ISSUE_ASSIGNEES = Template("""
    mutation AddAssigneesToAssignable($assignableId: ID!, $assigneeIds: [ID!]!) {
        addAssigneesToAssignable(input: { assignableId: $assignableId, assigneeIds: $assigneeIds }) {
            assignable { 
                assignees (first: 10) { nodes { name } }     
            }
        }
    }
    """)

    MUTATION_REMOVE_ISSUE_LABELS = Template("""
    mutation ($labelableId: ID!, $labelIds: [ID!]!) {
        removeLabelsFromLabelable(input: { labelableId: $labelableId, labelIds: $labelIds }) {
            labelable {
                ... on Issue {
                    labels (first: 100) { nodes { id name } }
                }
            }
        }
    }
    """)

    MUTATION_REMOVE_ISSUE_ASSIGNEES = Template("""
    mutation ($assignableId: ID!, $assigneeIds: [ID!]!) {
        removeAssigneesFromAssignable(input: { assignableId: $assignableId, assigneeIds: $assigneeIds }) {
            assignable {
                ... on Issue {
                    assignees (first: 100) { nodes { id name } }
                }
            }
        }
    }
    """)

    QUERY_LIST_PROJECT_VIEWS = Template("""
    query ProjectViews($owner: String!, $repo_name: String!, $project_number: Int!) {
        repository(owner: $owner, name: $repo_name) {
            projectV2(number: $project_number) {
                id
                title
                views(first: 20) {
                    nodes {
                        id
                        name
                        number
                        layout
                        filter
                        fields(first: 20) {
                            nodes {
                                ... on ProjectV2FieldCommon {
                                    id
                                    name
                                    dataType
                                }
                            }
                        }
                        groupByFields(first: 10) {
                            nodes {
                                ... on ProjectV2FieldCommon {
                                    id
                                    name
                                    dataType
                                }
                            }
                        }
                        sortBy(first: 5) {
                            nodes {
                                direction
                                field {
                                    ... on ProjectV2FieldCommon {
                                        id
                                        name
                                        dataType
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    """)

    # GraphQL query template for fetching project items filtered by view
    QUERY_PROJECT_ITEMS_BY_VIEW = Template("""
    query GetProjectItemsWithViewFilter($project_id: ID!, $view_number: Int!, $items_count: Int!, $after_cursor: String) {
      node(id: $project_id) {
        ... on ProjectV2 {
          title
          url
          view(number: $view_number) {
            id
            name
            number
            filter
          }
          items(first: $items_count, after: $after_cursor) {
            nodes {
              id
              type
              fieldValues(first: 30) {
                nodes {
                  ... on ProjectV2ItemFieldTextValue {
                    field { ... on ProjectV2FieldCommon { id name } }
                    text
                  }
                  ... on ProjectV2ItemFieldDateValue {
                    field { ... on ProjectV2FieldCommon { id name } }
                    date
                  }
                  ... on ProjectV2ItemFieldSingleSelectValue {
                    field { ... on ProjectV2FieldCommon { id name } }
                    name
                    optionId
                  }
                }
              }
              content {
                ... on Issue {
                  id
                  number
                  title
                  state
                  url
                  createdAt
                  updatedAt
                  labels(first: 10) {
                    nodes { id name color }
                  }
                  assignees(first: 5) {
                    nodes { id login name }
                  }
                }
                ... on PullRequest {
                  id
                  number
                  title
                  state
                  url
                  createdAt
                  updatedAt
                }
                ... on DraftIssue {
                  id
                  title
                  createdAt
                }
              }
            }
            pageInfo {
              hasNextPage
              endCursor
            }
            totalCount
          }
        }
      }
    }
    """)