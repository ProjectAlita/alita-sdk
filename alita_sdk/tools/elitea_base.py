import ast
import fnmatch
import logging
import traceback
from typing import Any, Optional, List, Dict
from langchain_core.tools import ToolException
from pydantic import BaseModel, create_model, Field
from .utils import TOOLKIT_SPLITTER

logger = logging.getLogger(__name__)

LoaderSchema = create_model(
    "LoaderSchema",
    branch=(Optional[str], Field(
        description="The branch to set as active before listing files. If None, the current active branch is used.")),
    whitelist=(Optional[List[str]],
               Field(description="A list of file extensions or paths to include. If None, all files are included.")),
    blacklist=(Optional[List[str]],
               Field(description="A list of file extensions or paths to exclude. If None, no files are excluded."))
)

# Base Vector Store Schema Models
BaseIndexParams = create_model(
    "BaseIndexParams",
    collection_suffix=(Optional[str], Field(description="Optional suffix for collection name (max 7 characters)", default="", max_length=7)),
    vectorstore_type=(Optional[str], Field(description="Vectorstore type (Chroma, PGVector, Elastic, etc.)", default="PGVector")),
)

BaseCodeIndexParams = create_model(
    "BaseCodeIndexParams",
    collection_suffix=(Optional[str], Field(description="Optional suffix for collection name (max 7 characters)", default="", max_length=7)),
    vectorstore_type=(Optional[str], Field(description="Vectorstore type (Chroma, PGVector, Elastic, etc.)", default="PGVector")),
    branch=(Optional[str], Field(description="Branch to index files from. Defaults to active branch if None.", default=None)),
    whitelist=(Optional[List[str]], Field(description="File extensions or paths to include. Defaults to all files if None.", default=None)),
    blacklist=(Optional[List[str]], Field(description="File extensions or paths to exclude. Defaults to no exclusions if None.", default=None)),
)

BaseSearchParams = create_model(
    "BaseSearchParams",
    query=(str, Field(description="Query text to search in the index")),
    collection_suffix=(Optional[str], Field(description="Optional suffix for collection name (max 7 characters)", default="", max_length=7)),
    vectorstore_type=(Optional[str], Field(description="Vectorstore type (Chroma, PGVector, Elastic, etc.)", default="PGVector")),
    filter=(Optional[dict | str], Field(
        description="Filter to apply to the search results. Can be a dictionary or a JSON string.",
        default={},
        examples=["{\"key\": \"value\"}", "{\"status\": \"active\"}"]
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

BaseStepbackSearchParams = create_model(
    "BaseStepbackSearchParams",
    query=(str, Field(description="Query text to search in the index")),
    collection_suffix=(Optional[str], Field(description="Optional suffix for collection name (max 7 characters)", default="", max_length=7)),
    vectorstore_type=(Optional[str], Field(description="Vectorstore type (Chroma, PGVector, Elastic, etc.)", default="PGVector")),
    messages=(Optional[List], Field(description="Chat messages for stepback search context", default=[])),
    filter=(Optional[dict | str], Field(
        description="Filter to apply to the search results. Can be a dictionary or a JSON string.",
        default={},
        examples=["{\"key\": \"value\"}", "{\"status\": \"active\"}"]
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


class BaseToolApiWrapper(BaseModel):

    def get_available_tools(self):
        raise NotImplementedError("Subclasses should implement this method")

    def run(self, mode: str, *args: Any, **kwargs: Any):
        if TOOLKIT_SPLITTER in mode:
            mode = mode.rsplit(TOOLKIT_SPLITTER, maxsplit=1)[1]
        for tool in self.get_available_tools():
            if tool["name"] == mode:
                try:
                    execution = tool["ref"](*args, **kwargs)
                    # if not isinstance(execution, str):
                    #     execution = str(execution)
                    return execution
                except Exception as e:
                    # Catch all tool execution exceptions and provide user-friendly error messages
                    error_type = type(e).__name__
                    error_message = str(e)
                    full_traceback = traceback.format_exc()
                    
                    # Log the full exception details for debugging
                    logger.error(f"Tool execution failed for '{mode}': {error_type}: {error_message}")
                    logger.error(f"Full traceback:\n{full_traceback}")
                    logger.debug(f"Tool execution parameters - args: {args}, kwargs: {kwargs}")
                    
                    # Provide specific error messages for common issues
                    if isinstance(e, TypeError) and "unexpected keyword argument" in error_message:
                        # Extract the problematic parameter name from the error message
                        import re
                        match = re.search(r"unexpected keyword argument '(\w+)'", error_message)
                        if match:
                            bad_param = match.group(1)
                            # Try to get expected parameters from the tool's args_schema if available
                            expected_params = "unknown"
                            if "args_schema" in tool and hasattr(tool["args_schema"], "__fields__"):
                                expected_params = list(tool["args_schema"].__fields__.keys())
                            
                            user_friendly_message = (
                                f"Parameter error in tool '{mode}': unexpected parameter '{bad_param}'. "
                                f"Expected parameters: {expected_params}\n\n"
                                f"Full traceback:\n{full_traceback}"
                            )
                        else:
                            user_friendly_message = (
                                f"Parameter error in tool '{mode}': {error_message}\n\n"
                                f"Full traceback:\n{full_traceback}"
                            )
                    elif isinstance(e, TypeError):
                        user_friendly_message = (
                            f"Parameter error in tool '{mode}': {error_message}\n\n"
                            f"Full traceback:\n{full_traceback}"
                        )
                    elif isinstance(e, ValueError):
                        user_friendly_message = (
                            f"Value error in tool '{mode}': {error_message}\n\n"
                            f"Full traceback:\n{full_traceback}"
                        )
                    elif isinstance(e, KeyError):
                        user_friendly_message = (
                            f"Missing required configuration or data in tool '{mode}': {error_message}\n\n"
                            f"Full traceback:\n{full_traceback}"
                        )
                    elif isinstance(e, ConnectionError):
                        user_friendly_message = (
                            f"Connection error in tool '{mode}': {error_message}\n\n"
                            f"Full traceback:\n{full_traceback}"
                        )
                    elif isinstance(e, TimeoutError):
                        user_friendly_message = (
                            f"Timeout error in tool '{mode}': {error_message}\n\n"
                            f"Full traceback:\n{full_traceback}"
                        )
                    else:
                        user_friendly_message = (
                            f"Tool '{mode}' execution failed: {error_type}: {error_message}\n\n"
                            f"Full traceback:\n{full_traceback}"
                        )
                    
                    # Re-raise with the user-friendly message while preserving the original exception
                    raise ToolException(user_friendly_message) from e
        else:
            raise ValueError(f"Unknown mode: {mode}. "
                             f"Available modes: {', '.join([tool['name'] for tool in self.get_available_tools()])}. "
                             f"Review the tool's name in your request.")


class BaseVectorStoreToolApiWrapper(BaseToolApiWrapper):
    """Base class for tool API wrappers that support vector store functionality."""
    
    def _init_vector_store(self, collection_suffix: str = "", embeddings: Optional[Any] = None):
        """ Initializes the vector store wrapper with the provided parameters."""
        try:
            from alita_sdk.runtime.tools.vectorstore import VectorStoreWrapper
        except ImportError:
            from alita_sdk.runtime.tools.vectorstore import VectorStoreWrapper
        
        # Validate collection_suffix length
        if collection_suffix and len(collection_suffix.strip()) > 7:
            raise ToolException("collection_suffix must be 7 characters or less")
        
        # Create collection name with suffix if provided
        collection_name = str(self.collection_name)
        if collection_suffix and collection_suffix.strip():
            collection_name = f"{self.collection_name}_{collection_suffix.strip()}"
        
        if self.vectorstore_type == 'PGVector':
            vectorstore_params = {
                "use_jsonb": True,
                "collection_name": collection_name,
                "create_extension": True,
                "alita_sdk_options": {
                    "target_schema": collection_name,
                },
                "connection_string": self.connection_string.get_secret_value()
            }
        elif self.vectorstore_type == 'Chroma':
            vectorstore_params = {
                "collection_name": collection_name,
                "persist_directory": "./indexer_db"
            }

        return VectorStoreWrapper(
            llm=self.llm,
            vectorstore_type=self.vectorstore_type,
            embedding_model=self.embedding_model,
            embedding_model_params=self.embedding_model_params,
            vectorstore_params=vectorstore_params,
            embeddings=embeddings
        )

    def search_index(self,
                     query: str,
                     collection_suffix: str = "",
                     filter: dict | str = {}, cut_off: float = 0.5,
                     search_top: int = 10, reranker: dict = {},
                     full_text_search: Optional[Dict[str, Any]] = None,
                     reranking_config: Optional[Dict[str, Dict[str, Any]]] = None,
                     extended_search: Optional[List[str]] = None,
                     **kwargs):
        """ Searches indexed documents in the vector store."""
        vectorstore = self._init_vector_store(collection_suffix)
        return vectorstore.search_documents(
            query, 
            doctype=self.doctype, 
            filter=filter, 
            cut_off=cut_off, 
            search_top=search_top, 
            reranker=reranker,
            full_text_search=full_text_search, 
            reranking_config=reranking_config, 
            extended_search=extended_search
        )

    def stepback_search_index(self,
                     query: str,
                     messages: List[Dict[str, Any]] = [],
                     collection_suffix: str = "",
                     filter: dict | str = {}, cut_off: float = 0.5,
                     search_top: int = 10, reranker: dict = {},
                     full_text_search: Optional[Dict[str, Any]] = None,
                     reranking_config: Optional[Dict[str, Dict[str, Any]]] = None,
                     extended_search: Optional[List[str]] = None,
                     **kwargs):
        """ Searches indexed documents in the vector store."""
        vectorstore = self._init_vector_store(collection_suffix)
        return vectorstore.stepback_search(
            query, 
            messages, 
            self.doctype, 
            filter=filter, 
            cut_off=cut_off, 
            search_top=search_top,
            full_text_search=full_text_search, 
            reranking_config=reranking_config, 
            extended_search=extended_search
        )

    def stepback_summary_index(self,
                     query: str,
                     messages: List[Dict[str, Any]] = [],
                     collection_suffix: str = "",
                     filter: dict | str = {}, cut_off: float = 0.5,
                     search_top: int = 10, reranker: dict = {},
                     full_text_search: Optional[Dict[str, Any]] = None,
                     reranking_config: Optional[Dict[str, Dict[str, Any]]] = None,
                     extended_search: Optional[List[str]] = None,
                     **kwargs):
        """ Generates a summary of indexed documents using stepback technique."""
        vectorstore = self._init_vector_store(collection_suffix)
        return vectorstore.stepback_summary(
            query, 
            messages, 
            self.doctype, 
            filter=filter, 
            cut_off=cut_off, 
            search_top=search_top,
            full_text_search=full_text_search, 
            reranking_config=reranking_config, 
            extended_search=extended_search
        )

    def _get_vector_search_tools(self):
        """
        Returns the standardized vector search tools (search operations only).
        Index operations are toolkit-specific and should be added manually to each toolkit.
        
        Returns:
            List of tool dictionaries with name, ref, description, and args_schema
        """
        return [
            {
                "name": "search_index",
                "mode": "search_index",
                "ref": self.search_index,
                "description": self.search_index.__doc__,
                "args_schema": BaseSearchParams
            },
            {
                "name": "stepback_search_index",
                "mode": "stepback_search_index",
                "ref": self.stepback_search_index,
                "description": self.stepback_search_index.__doc__,
                "args_schema": BaseStepbackSearchParams
            },
            {
                "name": "stepback_summary_index",
                "mode": "stepback_summary_index",
                "ref": self.stepback_summary_index,
                "description": self.stepback_summary_index.__doc__,
                "args_schema": BaseStepbackSearchParams
            }
        ]


class BaseCodeToolApiWrapper(BaseVectorStoreToolApiWrapper):

    def _get_files(self):
        raise NotImplementedError("Subclasses should implement this method")

    def _read_file(self, file_path: str, branch: str):
        raise NotImplementedError("Subclasses should implement this method")

    def __handle_get_files(self, path: str, branch: str):
        """
        Handles the retrieval of files from a specific path and branch.
        This method should be implemented in subclasses to provide the actual file retrieval logic.
        """
        _files = self._get_files(path, branch)
        if isinstance(_files, str):
            try:
                # Attempt to convert the string to a list using ast.literal_eval
                _files = ast.literal_eval(_files)
                # Ensure that the result is actually a list of strings
                if not isinstance(_files, list) or not all(isinstance(item, str) for item in _files):
                    raise ValueError("The evaluated result is not a list of strings")
            except (SyntaxError, ValueError):
                # Handle the case where the string cannot be converted to a list
                raise ValueError("Expected a list of strings, but got a string that cannot be converted")

            # Ensure _files is a list of strings
        if not isinstance(_files, list) or not all(isinstance(item, str) for item in _files):
            raise ValueError("Expected a list of strings")
        return _files

    def loader(self,
               branch: Optional[str] = None,
               whitelist: Optional[List[str]] = None,
               blacklist: Optional[List[str]] = None) -> str:
        """
        Generates file content from a branch, respecting whitelist and blacklist patterns.

        Parameters:
        - branch (Optional[str]): Branch for listing files. Defaults to the current branch if None.
        - whitelist (Optional[List[str]]): File extensions or paths to include. Defaults to all files if None.
        - blacklist (Optional[List[str]]): File extensions or paths to exclude. Defaults to no exclusions if None.

        Returns:
        - generator: Yields content from files matching the whitelist but not the blacklist.

        Example:
        # Use 'feature-branch', include '.py' files, exclude 'test_' files
        file_generator = loader(branch='feature-branch', whitelist=['*.py'], blacklist=['*test_*'])

        Notes:
        - Whitelist and blacklist use Unix shell-style wildcards.
        - Files must match the whitelist and not the blacklist to be included.
        """
        from .chunkers.code.codeparser import parse_code_files_for_db

        _files = self.__handle_get_files("", branch or self.active_branch)

        logger.info(f"Files in branch: {_files}")

        def is_whitelisted(file_path: str) -> bool:
            if whitelist:
                return any(fnmatch.fnmatch(file_path, pattern) for pattern in whitelist)
            return True

        def is_blacklisted(file_path: str) -> bool:
            if blacklist:
                return any(fnmatch.fnmatch(file_path, pattern) for pattern in blacklist)
            return False

        def file_content_generator():
            for file in _files:
                if is_whitelisted(file) and not is_blacklisted(file):
                    yield {"file_name": file,
                           "file_content": self._read_file(file, branch=branch or self.active_branch)}

        return parse_code_files_for_db(file_content_generator())
    
    def index_data(self,
                   branch: Optional[str] = None,
                   whitelist: Optional[List[str]] = None,
                   blacklist: Optional[List[str]] = None,
                   collection_suffix: str = "",
                   **kwargs) -> str:
        """Index repository files in the vector store using code parsing."""
        
        
        
        documents = self.loader(
            branch=branch,
            whitelist=whitelist,
            blacklist=blacklist
        )
        vectorstore = self._init_vector_store(collection_suffix)
        return vectorstore.index_documents(documents)

    def _get_vector_search_tools(self):
        """
        Override the base method to include the index_data tool for code-based toolkits.
        
        Returns:
            List: A list of vector search tools including index_data and search tools.
        """
        # Get the base search tools (search_index, stepback_search_index, stepback_summary_index)
        base_tools = super()._get_vector_search_tools()
        
        # Add the index_data tool specific to code toolkits
        index_tool = {
            "name": "index_data",
            "mode": "index_data",
            "ref": self.index_data,
            "description": self.index_data.__doc__,
            "args_schema": BaseCodeIndexParams
        }
        
        # Return index_data tool first, then the search tools
        return [index_tool] + base_tools