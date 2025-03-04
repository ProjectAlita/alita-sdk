# jira_connect.py

**Path:** `src/alita_sdk/community/eda/jira/jira_connect.py`

## Data Flow

The data flow within `jira_connect.py` revolves around connecting to a Jira instance, retrieving project information, and processing this data into a structured format. The journey begins with user credentials and Jira instance details being passed to the `connect_to_jira` function. This function establishes a connection to Jira using the provided credentials. Once connected, the `connect_to_jira_and_print_projects` function retrieves the list of projects accessible to the authenticated user. The project information, including project keys and names, is then processed and stored in a pandas DataFrame. This DataFrame is subsequently saved to a CSV file for further use. The data flow is linear, starting from input parameters, moving through connection and data retrieval, and ending with data storage.

Example:
```python
jira = JIRA(
    server=jira_base_url,
    options=jira_options,
    basic_auth=(jira_username, jira_api_key) if jira_api_key else None,
    token_auth=jira_token if jira_token else None
)
# Establishes a connection to Jira using the provided credentials
```

## Functions Descriptions

### connect_to_jira

This function is responsible for establishing a connection to a Jira instance using the provided credentials. It takes the following parameters:
- `jira_base_url`: The base URL of the Jira instance.
- `jira_verify_ssl`: A boolean indicating whether to verify SSL certificates.
- `jira_username`: The username for Jira authentication.
- `jira_api_key`: The API key for Jira authentication.
- `jira_token`: The token for Jira authentication.

The function constructs a `JIRA` object using these parameters and returns it. If the API key is provided, it uses basic authentication; otherwise, it uses token authentication.

Example:
```python
jira = JIRA(
    server=jira_base_url,
    options=jira_options,
    basic_auth=(jira_username, jira_api_key) if jira_api_key else None,
    token_auth=jira_token if jira_token else None
)
# Returns a JIRA object for interacting with the Jira instance
```

### connect_to_jira_and_print_projects

This function retrieves information about all projects accessible to the authenticated user. It first establishes a connection to Jira using the `connect_to_jira` function if a `JIRA` object is not provided. It then retrieves the list of projects and processes their keys and names into a pandas DataFrame. The DataFrame is saved to a CSV file. The function returns the `JIRA` object and the DataFrame.

Example:
```python
projects = jira.projects()
prj_keys = [prj.key for prj in projects]
prj_names = [prj.name for prj in projects]
# Retrieves project keys and names from the Jira instance
```

### create_df_from_dict_and_save

This function creates a pandas DataFrame from a dictionary containing project information and saves it to a CSV file. It takes the following parameter:
- `prj_info`: A dictionary containing project keys and names.

The function constructs the DataFrame, sets the index, and saves it to the specified path.

Example:
```python
df_prj = pd.DataFrame.from_dict(prj_info)
df_prj.index = df_prj.index + 1
df_prj.to_csv(OUTPUT_PROJECTS_PATH, index=True)
# Creates a DataFrame and saves it to a CSV file
```

## Dependencies Used and Their Descriptions

### jira

The `jira` module is used to interact with the Jira instance. It provides the `JIRA` class, which is used to establish a connection and perform various operations on the Jira instance. The module is imported as follows:
```python
from jira import JIRA, JIRAError
```

### pandas

The `pandas` library is used for data manipulation and analysis. In this file, it is used to create DataFrames and save them to CSV files. The module is imported as follows:
```python
import pandas as pd
```

### logging

The `logging` module is used for logging messages. It provides a way to configure different log levels and output formats. The module is imported as follows:
```python
import logging
```

### Optional and Tuple

These are type hints from the `typing` module, used to specify optional parameters and return types. They are imported as follows:
```python
from typing import Optional, Tuple
```

### read_config and constants

These are custom modules used to read configuration settings and define constants. They are imported as follows:
```python
from ..utils.read_config import JiraConfig, Config
from ..utils.constants import OUTPUT_PROJECTS_PATH
```

## Functional Flow

The functional flow of `jira_connect.py` begins with the `connect_to_jira` function, which establishes a connection to the Jira instance. If the connection is successful, the `connect_to_jira_and_print_projects` function retrieves the list of projects and processes their information into a pandas DataFrame. The DataFrame is then saved to a CSV file using the `create_df_from_dict_and_save` function. The flow is straightforward, with each function performing a specific task and passing the results to the next function.

Example:
```python
jira = connect_to_jira(jira_base_url, jira_verify_ssl, jira_username, jira_api_key, jira_token)
if jira:
    jira, df_prj = connect_to_jira_and_print_projects(jira)
# Establishes a connection and retrieves project information
```

## Endpoints Used/Created

The `jira_connect.py` file does not explicitly define or call any endpoints. Instead, it uses the `JIRA` class from the `jira` module to interact with the Jira instance. The endpoints and their interactions are abstracted away by the `JIRA` class methods, such as `projects()`, which retrieves the list of projects accessible to the authenticated user.
