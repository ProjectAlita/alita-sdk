# jira_sprints.py

**Path:** `src/alita_sdk/community/eda/jira/jira_sprints.py`

## Data Flow

The data flow within the `jira_sprints.py` file revolves around extracting and processing sprints data from Jira. The data originates from the Jira API, specifically from the boards and sprints endpoints. The data is then transformed into pandas DataFrames for further analysis. The journey of data begins with the initialization of the `JiraSprints` class, where the Jira instance and project keys are provided. The `sprints_all_data_to_dataframe` method orchestrates the data extraction process by iterating over the projects and retrieving the boards and their respective sprints. The data is temporarily stored in lists and DataFrames before being returned as a consolidated DataFrame.

Example:
```python
class JiraSprints(JiraBasic):
    def __init__(self, jira: JIRA, projects: str):
        super().__init__(jira, projects)
        self.board_type = 'scrum'

    def sprints_all_data_to_dataframe(self) -> pd.DataFrame:
        projects_list = self.projects.strip().replace(" ", "").split(',')
        df_sprints = pd.DataFrame()
        for project in projects_list:
            boards = self._get_boards(board_type=self.board_type, project=project)
            boards_ids = self._get_boards_ids(boards)
            if not boards_ids:
                return pd.DataFrame()
            df_sprints = self._sprints_data_one_project_to_dataframe(boards_ids, project, df_sprints)
        return df_sprints
```
In this example, the `sprints_all_data_to_dataframe` method extracts sprints data for multiple projects and consolidates it into a single DataFrame.

## Functions Descriptions

1. `__init__(self, jira: JIRA, projects: str)`: Initializes the `JiraSprints` class with a Jira instance and project keys. It sets the board type to 'scrum'.

2. `sprints_all_data_to_dataframe(self) -> pd.DataFrame`: Extracts sprints data for multiple projects and consolidates it into a single DataFrame. It iterates over the projects, retrieves the boards and their respective sprints, and returns the consolidated DataFrame.

3. `_get_boards(self, board_type: str = None, board_name: str = None, project: str = None) -> list`: Extracts boards from Jira for a given project. It handles pagination and retries in case of errors.

4. `_get_boards_ids(self, boards: list) -> list`: Extracts board IDs from the boards' attributes.

5. `_sprints_data_one_project_to_dataframe(self, boards_ids: list, project: str, df_sprints_all_projects: pd.DataFrame) -> pd.DataFrame`: Extracts sprints data for a single project and concatenates it with the input DataFrame.

6. `_get_sprints(self, board_id: int, extended: Optional[bool] = None, state: str = None) -> list`: Extracts sprints from Jira for a given board ID. It handles pagination and retries in case of errors.

7. `_get_sprints_info(sprints_list: list) -> pd.DataFrame`: Extracts sprints data from the sprints' attributes and converts it into a DataFrame.

## Dependencies Used and Their Descriptions

1. `logging`: Used for logging error messages.

2. `pandas`: Used for creating and manipulating DataFrames.

3. `retry`: Used for retrying operations in case of errors.

4. `jira`: Used for interacting with the Jira API.

5. `string_to_datetime`: A utility function for converting strings to datetime objects.

6. `JiraBasic`: A base class that provides common Jira functionalities.

7. `CircuitBreaker`, `CircuitOpenException`: Used for implementing circuit breaker pattern to handle failures.

## Functional Flow

The functional flow of the `jira_sprints.py` file begins with the initialization of the `JiraSprints` class. The `sprints_all_data_to_dataframe` method is the main entry point for extracting sprints data. It iterates over the projects, retrieves the boards, and then retrieves the sprints for each board. The data is consolidated into a single DataFrame and returned. The helper methods `_get_boards`, `_get_boards_ids`, `_sprints_data_one_project_to_dataframe`, `_get_sprints`, and `_get_sprints_info` are used to break down the data extraction process into smaller, manageable steps.

## Endpoints Used/Created

1. `jira.boards(start_at, max_results, board_type, board_name, project)`: Retrieves boards from Jira for a given project.

2. `jira.sprints(board_id, extended, start_at, max_results, state)`: Retrieves sprints from Jira for a given board ID.
