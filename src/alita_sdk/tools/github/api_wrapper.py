from typing import Any, Dict, List, Optional, Union, Tuple
import logging
import traceback
import json
import re
from pydantic import BaseModel, model_validator, Field, SecretStr

from .github_client import GitHubClient
from .graphql_client_wrapper import GraphQLClientWrapper
from .schemas import (
    GitHubAuthConfig,
    GitHubRepoConfig
)

from ..elitea_base import BaseVectorStoreToolApiWrapper

from langchain_core.callbacks import dispatch_custom_event

logger = logging.getLogger(__name__)

# Import prompts for tools
from .tool_prompts import (
    UPDATE_FILE_PROMPT,
    CREATE_ISSUE_PROMPT,
    UPDATE_ISSUE_PROMPT,
    CREATE_ISSUE_ON_PROJECT_PROMPT,
    UPDATE_ISSUE_ON_PROJECT_PROMPT
)

# Create schema models for the new indexing functionality
from pydantic import create_model
from typing import Literal

indexGitHubRepoParams = create_model(
    "indexGitHubRepoParams",
    whitelist=(Optional[List[str]], Field(description="File extensions or paths to include. Defaults to all files if None.", default=None)),
    blacklist=(Optional[List[str]], Field(description="File extensions or paths to exclude. Defaults to no exclusions if None.", default=None)),
    collection_suffix=(Optional[str], Field(description="Optional suffix for collection name (max 7 characters)", default="", max_length=7)),
)

searchGitHubIndexParams = create_model(
    "searchGitHubIndexParams",
    query=(str, Field(description="Query text to search in the index")),
    collection_suffix=(Optional[str], Field(description="Optional suffix for collection name (max 7 characters)", default="", max_length=7)),
    filter=(Optional[dict | str], Field(
        description="Filter to apply to the search results. Can be a dictionary or a JSON string.",
        default={},
        examples=["{\"repository\": \"owner/repo\"}", "{\"branch\": \"main\"}"]
    )),
    cut_off=(Optional[float], Field(description="Cut-off score for search results", default=0.5)),
    search_top=(Optional[int], Field(description="Number of top results to return", default=10)),
    reranker=(Optional[dict], Field(
        description="Reranker configuration. Can be a dictionary with reranking parameters.",
        default={}
    )),
    full_text_search=(Optional[Dict[str, Any]], Field(
        description="Full text search parameters. Can be a dictionary with search options.",
        default=None
    )),
    reranking_config=(Optional[Dict[str, Dict[str, Any]]], Field(
        description="Reranking configuration. Can be a dictionary with reranking settings.",
        default=None
    )),
    extended_search=(Optional[List[str]], Field(
        description="List of additional fields to include in the search results.",
        default=None
    )),
)

stepbackSearchGitHubIndexParams = create_model(
    "stepbackSearchGitHubIndexParams",
    query=(str, Field(description="Query text to search in the index")),
    collection_suffix=(Optional[str], Field(description="Optional suffix for collection name (max 7 characters)", default="", max_length=7)),
    messages=(Optional[List], Field(description="Chat messages for stepback search context", default=[])),
    filter=(Optional[dict | str], Field(
        description="Filter to apply to the search results. Can be a dictionary or a JSON string.",
        default={},
        examples=["{\"repository\": \"owner/repo\"}", "{\"branch\": \"main\"}"]
    )),
    cut_off=(Optional[float], Field(description="Cut-off score for search results", default=0.5)),
    search_top=(Optional[int], Field(description="Number of top results to return", default=10)),
    reranker=(Optional[dict], Field(
        description="Reranker configuration. Can be a dictionary with reranking parameters.",
        default={}
    )),
    full_text_search=(Optional[Dict[str, Any]], Field(
        description="Full text search parameters. Can be a dictionary with search options.",
        default=None
    )),
    reranking_config=(Optional[Dict[str, Dict[str, Any]]], Field(
        description="Reranking configuration. Can be a dictionary with reranking settings.",
        default=None
    )),
    extended_search=(Optional[List[str]], Field(
        description="List of additional fields to include in the search results.",
        default=None
    )),
)


class AlitaGitHubAPIWrapper(BaseVectorStoreToolApiWrapper):
    """
    Wrapper for GitHub API that integrates both REST and GraphQL functionality.
    """
    # Authentication config
    github_access_token: Optional[str] = None
    github_username: Optional[str] = None
    github_password: Optional[str] = None
    github_app_id: Optional[str] = None
    github_app_private_key: Optional[str] = None
    github_base_url: Optional[str] = None

    # Repository config
    github_repository: Optional[str] = None
    active_branch: Optional[str] = None
    github_base_branch: Optional[str] = None

    # Add LLM instance
    llm: Optional[Any] = None

    # Vector store configuration
    connection_string: Optional[SecretStr] = None
    collection_name: Optional[str] = None
    doctype: Optional[str] = 'code'  # GitHub uses 'code' doctype
    embedding_model: Optional[str] = "HuggingFaceEmbeddings"
    embedding_model_params: Optional[Dict[str, Any]] = {"model_name": "sentence-transformers/all-MiniLM-L6-v2"}
    vectorstore_type: Optional[str] = "PGVector"

    # Client instances - renamed without leading underscores and marked as exclude=True
    github_client_instance: Optional[GitHubClient] = Field(default=None, exclude=True)
    graphql_client_instance: Optional[GraphQLClientWrapper] = Field(default=None, exclude=True)

    class Config:
        arbitrary_types_allowed = True

    @model_validator(mode='before')
    @classmethod
    def validate_environment(cls, values: Dict) -> Dict:
        """
        Initialize GitHub clients based on the provided values.

        Args:
            values (Dict): Configuration values for GitHub API wrapper

        Returns:
            Dict: Updated values dictionary
        """
        from langchain.utils import get_from_dict_or_env

        # Get all authentication values
        github_access_token = get_from_dict_or_env(values, "github_access_token", "GITHUB_ACCESS_TOKEN", default='')
        github_username = get_from_dict_or_env(values, "github_username", "GITHUB_USERNAME", default='')
        github_password = get_from_dict_or_env(values, "github_password", "GITHUB_PASSWORD", default='')
        github_app_id = get_from_dict_or_env(values, "github_app_id", "GITHUB_APP_ID", default='')
        github_app_private_key = get_from_dict_or_env(values, "github_app_private_key", "GITHUB_APP_PRIVATE_KEY", default='')
        github_base_url = get_from_dict_or_env(values, "github_base_url", "GITHUB_BASE_URL", default='https://api.github.com')

        auth_config = GitHubAuthConfig(
            github_access_token=github_access_token,
            github_username=github_username,
            github_password=github_password,
            github_app_id=github_app_id,  # This will be None if not provided - GitHubAuthConfig should allow this
            github_app_private_key=github_app_private_key,
            github_base_url=github_base_url
        )

        # Rest of initialization code remains the same
        github_repository = get_from_dict_or_env(values, "github_repository", "GITHUB_REPOSITORY")
        github_repository = GitHubClient.clean_repository_name(github_repository)

        repo_config = GitHubRepoConfig(
            github_repository=github_repository,
            active_branch=get_from_dict_or_env(values, "active_branch", "ACTIVE_BRANCH", default='main'),  # Change from 'ai' to 'main'
            github_base_branch=get_from_dict_or_env(values, "github_base_branch", "GITHUB_BASE_BRANCH", default="main")
        )

        # Initialize GitHub client with keyword arguments
        github_client = GitHubClient(auth_config=auth_config, repo_config=repo_config)
        # Initialize GraphQL client with keyword argument
        graphql_client = GraphQLClientWrapper(github_graphql_instance=github_client.github_api._Github__requester)
        # Set client attributes on the class (renamed from _github_client to github_client_instance)
        values["github_client_instance"] = github_client
        values["graphql_client_instance"] = graphql_client

        # Update values
        values["github_repository"] = github_repository
        values["active_branch"] = repo_config.active_branch
        values["github_base_branch"] = repo_config.github_base_branch

        # Ensure LLM is available in values if needed
        if "llm" not in values:
            values["llm"] = None

        return values

    # Expose GitHub REST client methods directly via property
    @property
    def github_client(self) -> GitHubClient:
        """Access to GitHub REST client methods"""
        return self.github_client_instance

    # Expose GraphQL client methods directly via property
    @property
    def graphql_client(self) -> GraphQLClientWrapper:
        """Access to GitHub GraphQL client methods"""
        return self.graphql_client_instance


    def get_available_tools(self):
        # this is horrible, I need to think on something better
        if not self.github_client_instance:
            github_tools = GitHubClient.model_construct().get_available_tools()
        else:
            github_tools = self.github_client_instance.get_available_tools()
        if not self.graphql_client_instance:
            graphql_tools = GraphQLClientWrapper.model_construct().get_available_tools()
        else:
            graphql_tools = self.graphql_client_instance.get_available_tools()
            
        vector_store_tools = [
            {
                "name": "index_data",
                "ref": self.index_data,
                "mode": "index_data",
                "description": self.index_data.__doc__,
                "args_schema": indexGitHubRepoParams
            },
            {
                "name": "search_index",
                "ref": self.search_index,
                "mode": "search_index",
                "description": self.search_index.__doc__,
                "args_schema": searchGitHubIndexParams
            },
            {
                "name": "stepback_search_index",
                "ref": self.stepback_search_index,
                "mode": "stepback_search_index",
                "description": self.stepback_search_index.__doc__,
                "args_schema": stepbackSearchGitHubIndexParams
            }
        ]
        
        tools = github_tools + graphql_tools + vector_store_tools
        return tools

    def run(self, name: str, *args: Any, **kwargs: Any):
        for tool in self.get_available_tools():
            if tool["name"] == name:
                # Handle potential dictionary input for args when only one dict is passed
                if len(args) == 1 and isinstance(args[0], dict) and not kwargs:
                     kwargs = args[0]
                     args = () # Clear args
                try:
                    return tool["ref"](*args, **kwargs)
                except TypeError as e:
                     # Attempt to call with kwargs only if args fail and kwargs exist
                     if kwargs and not args:
                         try:
                             return tool["ref"](**kwargs)
                         except TypeError:
                             raise ValueError(f"Argument mismatch for tool '{name}'. Error: {e}") from e
                     else:
                         raise ValueError(f"Argument mismatch for tool '{name}'. Error: {e}") from e
        else:
            raise ValueError(f"Unknown tool name: {name}")

    def index_data(self,
                   whitelist: Optional[List[str]] = None,
                   blacklist: Optional[List[str]] = None,
                   collection_suffix: str = "",
                   **kwargs) -> str:
        """Index GitHub repository files in the vector store using code parsing."""
        
        try:
            from alita_sdk.langchain.interfaces.llm_processor import get_embeddings
        except ImportError:
            from src.alita_sdk.langchain.interfaces.llm_processor import get_embeddings
        
        documents = self.github_client_instance.loader(
            branch=self.active_branch,
            whitelist=whitelist,
            blacklist=blacklist,
            repo_name=self.github_repository
        )
        vectorstore = self._init_vector_store(collection_suffix)
        return vectorstore.index_documents(documents)
