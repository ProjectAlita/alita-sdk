# jira_statuses.py

**Path:** `src/alita_sdk/community/eda/jira/jira_statuses.py`

## Data Flow

The data flow within the `jira_statuses.py` file revolves around the retrieval of status information from a Jira instance. The process begins with the `get_all_statuses_list` function, which either accepts an existing Jira connection object or establishes a new connection using the `connect_to_jira` function. Once connected, the function retrieves all statuses from the Jira instance and extracts their names into a list. This list is then returned as the output. The data flow can be summarized as follows:

1. **Input:** Jira connection object (optional)
2. **Process:** Connect to Jira (if no connection object is provided) and retrieve statuses
3. **Output:** List of status names

Example:
```python
from jira import JIRA
from .jira_connect import connect_to_jira

def get_all_statuses_list(jira: JIRA) -> Optional[list]:
    """Get all statuses names."""
    if not jira:
        jira = connect_to_jira()
    if not jira:
        raise ConnectionError('Failed to connect to Jira')
    statuses = jira.statuses()
    return [status.name for status in statuses]
```
In this example, the `statuses` variable holds the list of status objects retrieved from Jira, and the list comprehension extracts the `name` attribute from each status object.

## Functions Descriptions

### `get_all_statuses_list`

The `get_all_statuses_list` function is responsible for retrieving the names of all statuses in a Jira instance. It takes an optional Jira connection object as a parameter. If the connection object is not provided, it attempts to establish a new connection using the `connect_to_jira` function. If the connection fails, a `ConnectionError` is raised. Once connected, the function retrieves the statuses from Jira and returns a list of their names.

- **Parameters:**
  - `jira` (JIRA): An optional Jira connection object.
- **Returns:**
  - `Optional[list]`: A list of status names or `None` if the connection fails.
- **Raises:**
  - `ConnectionError`: If the connection to Jira fails.

Example:
```python
jira = connect_to_jira()
status_names = get_all_statuses_list(jira)
print(status_names)
```
In this example, the `connect_to_jira` function is used to establish a connection to Jira, and the `get_all_statuses_list` function retrieves the status names, which are then printed.

## Dependencies Used and Their Descriptions

The `jira_statuses.py` file relies on the following dependencies:

- `typing.Optional`: Used for type hinting to indicate that a variable can be of a specified type or `None`.
- `jira.JIRA`: The Jira client library used to interact with the Jira instance.
- `connect_to_jira`: A function from the `jira_connect` module that establishes a connection to Jira.

These dependencies are essential for the functionality of the `get_all_statuses_list` function, as they provide the necessary tools for connecting to Jira and handling optional values.

## Functional Flow

The functional flow of the `jira_statuses.py` file is straightforward and involves the following steps:

1. **Import Dependencies:** The required modules and functions are imported.
2. **Define `get_all_statuses_list` Function:** The function is defined to retrieve status names from Jira.
3. **Check Jira Connection:** The function checks if a Jira connection object is provided. If not, it attempts to establish a new connection.
4. **Retrieve Statuses:** The function retrieves the statuses from Jira and extracts their names into a list.
5. **Return Status Names:** The list of status names is returned as the output.

Example:
```python
from typing import Optional
from jira import JIRA
from .jira_connect import connect_to_jira

def get_all_statuses_list(jira: JIRA) -> Optional[list]:
    """Get all statuses names."""
    if not jira:
        jira = connect_to_jira()
    if not jira:
        raise ConnectionError('Failed to connect to Jira')
    statuses = jira.statuses()
    return [status.name for status in statuses]
```
In this example, the functional flow is clearly defined, with each step logically following the previous one to achieve the desired outcome.

## Endpoints Used/Created

The `jira_statuses.py` file does not explicitly define or call any endpoints. However, it interacts with the Jira instance through the Jira client library (`jira.JIRA`). The `statuses` method of the Jira client is used to retrieve the list of statuses from the Jira instance. The interaction with Jira can be considered as an endpoint usage, where the Jira client library handles the communication with the Jira server.

Example:
```python
statuses = jira.statuses()
```
In this example, the `statuses` method is called on the Jira client object (`jira`) to retrieve the list of statuses from the Jira instance.