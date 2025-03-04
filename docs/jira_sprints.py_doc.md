# jira_sprints.py

**Path:** `src/alita_sdk/community/eda/jira/jira_sprints.py`

## Data Flow

The data flow within the `jira_sprints.py` file revolves around extracting and processing sprints data from Jira. The data journey begins with the initialization of the `JiraSprints` class, which requires an instance of the JIRA class and project keys. The primary method `sprints_all_data_to_dataframe` orchestrates the data extraction process by iterating over the provided projects, retrieving boards, and subsequently fetching sprints data for each board. The data is then transformed into a pandas DataFrame for further analysis.

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
In this snippet, the `sprints_all_data_to_dataframe` method processes data by iterating over projects, fetching boards, and extracting sprints data, which is then compiled into a DataFrame.

## Functions Descriptions

1. **`__init__`**: Initializes the `JiraSprints` class with JIRA instance and project keys. Sets the board type to 'scrum'.
   - **Parameters**: `jira` (JIRA instance), `projects` (str)
   - **Example**:
   ```python
   def __init__(self, jira: JIRA, projects: str):
       super().__init__(jira, projects)
       self.board_type = 'scrum'
   ```

2. **`sprints_all_data_to_dataframe`**: Extracts sprints data for multiple projects and compiles it into a DataFrame.
   - **Returns**: `pd.DataFrame`
   - **Example**:
   ```python
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

3. **`_get_boards`**: Retrieves boards from Jira for a specific project. Uses retry and circuit breaker mechanisms for robustness.
   - **Parameters**: `board_type` (str), `board_name` (str), `project` (str)
   - **Returns**: `list`
   - **Example**:
   ```python
   @retry((JIRAError, CircuitOpenException), tries=4, delay=5, backoff=2)
   @CircuitBreaker(max_failures=3, reset_timeout=5)
   def _get_boards(self, board_type: str = None, board_name: str = None, project: str = None) -> list:
       boards_list = []
       try:
           start_at = 0
           max_results = 50
           boards_batch = self.jira.boards(start_at, max_results, self.board_type, board_name, project)
           while boards_batch:
               boards_list.extend(boards_batch)
               start_at += max_results
               boards_batch = self.jira.boards(start_at, max_results, board_type, board_name, project)
       except JIRAError as err:
           logging.error(err.text)
       return boards_list
   ```

4. **`_get_boards_ids`**: Extracts board IDs from board objects.
   - **Parameters**: `boards` (list)
   - **Returns**: `list`
   - **Example**:
   ```python
   def _get_boards_ids(self, boards: list) -> list:
       if not boards:
           logging.info(f"There are no scrum boards in the projects {self.projects}")
           return []
       boards_params = [board.raw for board in boards]
       return [params.get('id') for params in boards_params]
   ```

5. **`_sprints_data_one_project_to_dataframe`**: Retrieves sprints data for a single project and appends it to the provided DataFrame.
   - **Parameters**: `boards_ids` (list), `project` (str), `df_sprints_all_projects` (pd.DataFrame)
   - **Returns**: `pd.DataFrame`
   - **Example**:
   ```python
   def _sprints_data_one_project_to_dataframe(self, boards_ids: list, project: str, df_sprints_all_projects: pd.DataFrame) -> pd.DataFrame:
       sprints_list = [self._get_sprints(board_id) for board_id in boards_ids]
       sprints_list = [item for sublist in sprints_list for item in sublist]
       df_sprints = self._get_sprints_info(sprints_list)
       df_sprints['project_key'] = project
       date_cols = [col for col in df_sprints.columns if 'Date' in col]
       df_sprints[date_cols] = df_sprints[date_cols].map(string_to_datetime)
       return pd.concat([df_sprints_all_projects, df_sprints], ignore_index=True)
   ```

6. **`_get_sprints`**: Extracts sprints from Jira for a specific board. Uses retry and circuit breaker mechanisms for robustness.
   - **Parameters**: `board_id` (int), `extended` (Optional[bool]), `state` (str)
   - **Returns**: `list`
   - **Example**:
   ```python
   @retry((JIRAError, CircuitOpenException), tries=4, delay=5, backoff=2)
   @CircuitBreaker(max_failures=3, reset_timeout=5)
   def _get_sprints(self, board_id: int, extended: Optional[bool] = None, state: str = None) -> list:
       sprints_list = []
       start_at = 0
       max_results = 50
       try:
           sprints_batch = self.jira.sprints(board_id, extended, start_at, max_results, state)
           while sprints_batch:
               sprints_list += sprints_batch
               start_at += max_results
               sprints_batch = self.jira.sprints(board_id, extended, start_at, max_results, state)
       except JIRAError as err:
           logging.error(err.text)
       return sprints_list
   ```

7. **`_get_sprints_info`**: Converts sprints data into a DataFrame.
   - **Parameters**: `sprints_list` (list)
   - **Returns**: `pd.DataFrame`
   - **Example**:
   ```python
   @staticmethod
   def _get_sprints_info(sprints_list: list) -> pd.DataFrame:
       if not sprints_list:
           return pd.DataFrame()
       sprints_info = [sprint.raw for sprint in sprints_list]
       return pd.DataFrame.from_records(sprints_info)
   ```

## Dependencies Used and Their Descriptions

1. **`logging`**: Used for logging error messages and information.
   - **Example**:
   ```python
   import logging
   logging.error(err.text)
   ```

2. **`pandas`**: Used for creating and manipulating DataFrames.
   - **Example**:
   ```python
   import pandas as pd
   df_sprints = pd.DataFrame()
   ```

3. **`retry`**: Used for retrying functions in case of exceptions.
   - **Example**:
   ```python
   from retry import retry
   @retry((JIRAError, CircuitOpenException), tries=4, delay=5, backoff=2)
   ```

4. **`JIRAError, JIRA`**: Used for interacting with Jira and handling Jira-specific errors.
   - **Example**:
   ```python
   from jira import JIRAError, JIRA
   ```

5. **`string_to_datetime`**: Utility function for converting strings to datetime objects.
   - **Example**:
   ```python
   from ..utils.convert_to_datetime import string_to_datetime
   ```

6. **`JiraBasic`**: Base class for Jira interactions.
   - **Example**:
   ```python
   from .jira_basic import JiraBasic
   ```

7. **`CircuitBreaker, CircuitOpenException`**: Used for implementing circuit breaker pattern to handle failures.
   - **Example**:
   ```python
   from ..utils.circuit_breaker import CircuitBreaker, CircuitOpenException
   ```

## Functional Flow

The functional flow of the `jira_sprints.py` file begins with the initialization of the `JiraSprints` class, which sets up the necessary attributes. The main method `sprints_all_data_to_dataframe` is called to extract and compile sprints data into a DataFrame. This method calls several helper methods to fetch boards, extract sprints, and process the data. The flow includes retry and circuit breaker mechanisms to handle potential failures and ensure robustness.

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
In this snippet, the `sprints_all_data_to_dataframe` method orchestrates the flow by iterating over projects, fetching boards, and extracting sprints data, which is then compiled into a DataFrame.

## Endpoints Used/Created

The `jira_sprints.py` file interacts with Jira endpoints to fetch boards and sprints data. These interactions are facilitated through the JIRA library.

1. **`jira.boards`**: Fetches boards for a specific project.
   - **Example**:
   ```python
   boards_batch = self.jira.boards(start_at, max_results, self.board_type, board_name, project)
   ```

2. **`jira.sprints`**: Fetches sprints for a specific board.
   - **Example**:
   ```python
   sprints_batch = self.jira.sprints(board_id, extended, start_at, max_results, state)
   ```
