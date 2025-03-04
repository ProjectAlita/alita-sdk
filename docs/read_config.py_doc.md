# read_config.py

**Path:** `src/alita_sdk/community/eda/utils/read_config.py`

## Data Flow

The data flow within the `read_config.py` file revolves around reading configuration files and initializing configuration objects for various platforms such as Jira, GitLab, GitHub, Azure DevOps, ClickUp, and SharePoint. The data originates from YAML configuration files, which are read and parsed into Python dictionaries. These dictionaries are then used to initialize configuration objects with specific attributes for each platform.

For example, the `read_config` method reads a YAML file and returns its contents as a dictionary:

```python
@staticmethod
 def read_config(file_path):
     """Read config YML file stored locally."""
     try:
         with open(file_path, 'r', encoding="utf-8") as yml_file:
             cfg = yaml.safe_load(yml_file)
             return cfg
     except (OSError, yaml.YAMLError) as err:
         logger.error('Could not open/read config file: %s', err)
         raise err
```

In this example, the `read_config` method reads the YAML file specified by `file_path`, parses it using `yaml.safe_load`, and returns the resulting dictionary `cfg`. This dictionary is then used to initialize the configuration objects.

## Functions Descriptions

### Config Class

The `Config` class is a base class for reading configuration files and initializing configuration objects. It has the following attributes and methods:

- `file_path`: The path to the configuration file.
- `platform`: The platform for which the configuration is being read.
- `__post_init__`: A method that is called after the object is initialized. It checks the configuration folder and reads the configuration file.
- `read_config`: A static method that reads the YAML configuration file and returns its contents as a dictionary.
- `check_configuration`: A static method that checks if the output folder exists and creates it if it does not.

### JiraConfig Class

The `JiraConfig` class inherits from the `Config` class and represents Jira credentials. It has the following attributes:

- `username`: The Jira username.
- `url`: The Jira URL.
- `token_or_password`: The Jira token or password.

### GitConfig Class

The `GitConfig` class inherits from the `Config` class and represents GitLab credentials. It has the following attributes:

- `url`: The GitLab URL.
- `token`: The GitLab token.

### GitHubConfig Class

The `GitHubConfig` class inherits from the `Config` class and represents GitHub credentials. It has the following attributes:

- `owner`: The GitHub owner.
- `token`: The GitHub token.

### AdoConfig Class

The `AdoConfig` class inherits from the `Config` class and represents Azure DevOps credentials. It has the following attributes:

- `organization`: The Azure DevOps organization.
- `user`: The Azure DevOps user.
- `token`: The Azure DevOps token.

### ClickUpConfig Class

The `ClickUpConfig` class inherits from the `Config` class and represents ClickUp credentials. It has the following attributes:

- `workspace_id`: The ClickUp workspace ID.
- `token`: The ClickUp token.

### SharePointConfig Class

The `SharePointConfig` class inherits from the `Config` class and represents SharePoint credentials. It has the following attributes:

- `client_id`: The SharePoint client ID.
- `url`: The SharePoint URL.
- `secret_name`: The SharePoint secret name.
- `client_secret`: The SharePoint client secret.

## Dependencies Used and Their Descriptions

The `read_config.py` file uses the following dependencies:

- `dataclasses`: Provides a decorator and functions for creating data classes.
- `os`: Provides a way of using operating system-dependent functionality such as reading or writing to the file system.
- `logging`: Provides a way to configure and use loggers in the application.
- `yaml`: Provides a way to parse YAML files.

These dependencies are used to read configuration files, log messages, and handle file system operations.

## Functional Flow

The functional flow of the `read_config.py` file involves the following steps:

1. The `Config` class is initialized with the path to the configuration file and the platform.
2. The `__post_init__` method is called, which checks the configuration folder and reads the configuration file.
3. The `read_config` method reads the YAML configuration file and returns its contents as a dictionary.
4. The specific configuration class (e.g., `JiraConfig`, `GitConfig`) initializes its attributes using the dictionary returned by `read_config`.

For example, the `JiraConfig` class initializes its attributes as follows:

```python
@dataclass
class JiraConfig(Config):
    """A class to represent JIRA credentials."""
    platform: str = "Jira"

    def __post_init__(self):
        super().__post_init__()
        self.username = self.cfg["username"]
        self.url = self.cfg["url"]
        self.token_or_password = self.cfg["token_or_password"]
```

In this example, the `JiraConfig` class calls the `__post_init__` method of the `Config` class to read the configuration file and then initializes its attributes (`username`, `url`, `token_or_password`) using the dictionary returned by `read_config`.

## Endpoints Used/Created

The `read_config.py` file does not explicitly define or call any endpoints. It focuses on reading local configuration files and initializing configuration objects for various platforms.