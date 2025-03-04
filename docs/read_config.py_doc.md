# read_config.py

**Path:** `src/alita_sdk/community/eda/utils/read_config.py`

## Data Flow

The data flow within the `read_config.py` file is centered around reading configuration files and initializing configuration objects for various platforms like Jira, GitLab, GitHub, ADO, ClickUp, and SharePoint. The data originates from YAML configuration files, which are read and parsed into Python dictionaries. These dictionaries are then used to initialize configuration objects with specific attributes for each platform.

The journey of data begins with the `Config` class, which reads the configuration file and extracts the relevant platform-specific configuration. This data is then used to initialize attributes in the subclasses representing different platforms. The data flow can be summarized as follows:

1. **Reading Configuration File:** The `read_config` method reads a YAML file and loads it into a Python dictionary.
2. **Initializing Configuration Objects:** The `__post_init__` method in each subclass extracts the relevant configuration data from the dictionary and initializes the object's attributes.
3. **Checking Configuration Folder:** The `check_configuration` method ensures that the output folder exists, creating it if necessary.

Example:
```python
@dataclass
class Config:
    file_path: str
    platform: str

    def __post_init__(self):
        self.check_configuration(OUTPUT_FOLDER)
        try:
            self.cfg = self.read_config(self.file_path)[self.platform]
        except ValueError:
            logger.error('A platform is not defined or it is not in a config')

    @staticmethod
    def read_config(file_path):
        try:
            with open(file_path, 'r', encoding="utf-8") as yml_file:
                cfg = yaml.safe_load(yml_file)
                return cfg
        except (OSError, yaml.YAMLError) as err:
            logger.error('Could not open/read config file: %s', err)
            raise err
```

## Functions Descriptions

### `Config` Class

The `Config` class is a base class for reading and storing configuration data. It has the following methods:

- `__post_init__`: This method is called after the object is initialized. It checks the configuration folder and reads the configuration file.
- `read_config`: This static method reads a YAML configuration file and returns its contents as a dictionary.
- `check_configuration`: This static method checks if the output folder exists and creates it if necessary.

### `JiraConfig` Class

The `JiraConfig` class inherits from `Config` and represents Jira credentials. It initializes the following attributes:

- `username`: The Jira username.
- `url`: The Jira URL.
- `token_or_password`: The Jira token or password.

### `GitConfig` Class

The `GitConfig` class inherits from `Config` and represents GitLab credentials. It initializes the following attributes:

- `url`: The GitLab URL.
- `token`: The GitLab token.

### `GitHubConfig` Class

The `GitHubConfig` class inherits from `Config` and represents GitHub credentials. It initializes the following attributes:

- `owner`: The GitHub owner.
- `token`: The GitHub token.

### `AdoConfig` Class

The `AdoConfig` class inherits from `Config` and represents ADO credentials. It initializes the following attributes:

- `organization`: The ADO organization.
- `user`: The ADO user.
- `token`: The ADO token.

### `ClickUpConfig` Class

The `ClickUpConfig` class inherits from `Config` and represents ClickUp credentials. It initializes the following attributes:

- `workspace_id`: The ClickUp workspace ID.
- `token`: The ClickUp token.

### `SharePointConfig` Class

The `SharePointConfig` class inherits from `Config` and represents SharePoint credentials. It initializes the following attributes:

- `client_id`: The SharePoint client ID.
- `url`: The SharePoint URL.
- `secret_name`: The SharePoint secret name.
- `client_secret`: The SharePoint client secret.

## Dependencies Used and Their Descriptions

The `read_config.py` file uses the following dependencies:

- `dataclasses`: Provides a decorator and functions for creating data classes.
- `os`: Used for interacting with the operating system, specifically for checking and creating directories.
- `logging`: Used for logging error and information messages.
- `yaml`: Used for parsing YAML configuration files.
- `constants`: Imports the `OUTPUT_FOLDER` constant, which specifies the output folder path.

Example:
```python
from dataclasses import dataclass
from os import path, mkdir
import logging
import yaml
from .constants import OUTPUT_FOLDER
```

## Functional Flow

The functional flow of the `read_config.py` file involves the following steps:

1. **Importing Dependencies:** The necessary modules and constants are imported.
2. **Defining the `Config` Class:** The base class for reading and storing configuration data is defined.
3. **Defining Subclasses:** Subclasses for different platforms (Jira, GitLab, GitHub, ADO, ClickUp, SharePoint) are defined, each initializing platform-specific attributes.
4. **Reading Configuration File:** The `read_config` method reads the YAML configuration file and returns its contents as a dictionary.
5. **Initializing Configuration Objects:** The `__post_init__` method in each subclass extracts the relevant configuration data and initializes the object's attributes.
6. **Checking Configuration Folder:** The `check_configuration` method ensures that the output folder exists, creating it if necessary.

Example:
```python
@dataclass
class JiraConfig(Config):
    platform: str = "Jira"

    def __post_init__(self):
        super().__post_init__()
        self.username = self.cfg["username"]
        self.url = self.cfg["url"]
        self.token_or_password = self.cfg["token_or_password"]
```

## Endpoints Used/Created

The `read_config.py` file does not explicitly define or call any endpoints. Its primary purpose is to read local configuration files and initialize configuration objects for various platforms.