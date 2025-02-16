"""This module reads config files with JIRA, ADO, and GitLab credentials or AWS configuration."""

from dataclasses import dataclass
from os import path, mkdir
import logging
import yaml


from .constants import OUTPUT_FOLDER

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class Config:
    """
    A base class to use the configuration file with Jira, ADO, and GitLab credentials.

    Attributes
        file_path: str
            path to a local file with credentials
    """
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
        """Read config YML file stored locally."""
        try:
            with open(file_path, 'r', encoding="utf-8") as yml_file:
                cfg = yaml.safe_load(yml_file)
                return cfg
        except (OSError, yaml.YAMLError) as err:
            logger.error('Could not open/read config file: %s', err)
            raise err

    @staticmethod
    def check_configuration(path_to_folder):
        """Check if the folder to store output file exists locally."""
        if not path.isdir(path_to_folder):
            try:
                mkdir(path_to_folder)
            except OSError as err:
                logger.error('Could not create directory: %s', err)


@dataclass
class JiraConfig(Config):
    """A class to represent JIRA credentials."""
    platform: str = "Jira"

    def __post_init__(self):
        super().__post_init__()
        self.username = self.cfg["username"]
        self.url = self.cfg["url"]
        self.token_or_password = self.cfg["token_or_password"]


@dataclass
class GitConfig(Config):
    """A class to represent GitLab credentials."""
    platform: str = "Git"

    def __post_init__(self):
        super().__post_init__()
        self.url = self.cfg["url"]
        self.token = self.cfg["token"]


@dataclass
class GitHubConfig(Config):
    """A class to represent GitHub credentials."""
    platform: str = "GitHub"

    def __post_init__(self):
        super().__post_init__()
        self.owner = self.cfg["owner"]
        self.token = self.cfg["token"]


@dataclass
class AdoConfig(Config):
    """A class to represent ADO credentials."""
    platform: str = "AzureDevOps"

    def __post_init__(self):
        super().__post_init__()
        self.organization = self.cfg["organization"]
        self.user = self.cfg["user"]
        self.token = self.cfg["token"]


@dataclass
class ClickUpConfig(Config):
    """A class to represent ClickUp credentials."""
    platform = "ClickUp"

    def __post_init__(self):
        super().__post_init__()
        self.workspace_id = self.cfg["workspace_id"]
        self.token = self.cfg["token"]


@dataclass
class SharePointConfig(Config):
    """A class to represent SharePoint credentials."""
    platform: str = "SharePoint"

    def __post_init__(self):
        super().__post_init__()
        self.client_id = self.cfg["client_id"]
        self.url = self.cfg["url"]
        self.secret_name = self.cfg["secret_name"]
        self.client_secret = self.cfg["token_or_password"]
