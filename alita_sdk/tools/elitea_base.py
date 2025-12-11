import ast
import fnmatch
import json
import logging
import traceback
from typing import Any, Optional, List, Literal, Dict, Generator

from langchain_core.documents import Document
from langchain_core.tools import ToolException
from pydantic import BaseModel, create_model, Field, SecretStr

# from alita_sdk.runtime.langchain.interfaces.llm_processor import get_embeddings
from .chunkers import markdown_chunker
from .vector_adapters.VectorStoreAdapter import VectorStoreAdapterFactory
from ..runtime.utils.utils import IndexerKeywords

logger = logging.getLogger(__name__)

INDEX_TOOL_NAMES = ['index_data', 'remove_index', 'list_collections', 'search_index', 'stepback_search_index',
                            'stepback_summary_index']

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
    index_name=(str, Field(description="Index name (max 7 characters)", min_length=1, max_length=7)),
)

BaseCodeIndexParams = create_model(
    "BaseCodeIndexParams",
    index_name=(str, Field(description="Index name (max 7 characters)", min_length=1, max_length=7)),
    clean_index=(Optional[bool], Field(default=False, description="Optional flag to enforce clean existing index before indexing new data")),
    progress_step=(Optional[int], Field(default=5, ge=0, le=100,
                         description="Optional step size for progress reporting during indexing")),
    branch=(Optional[str], Field(description="Branch to index files from. Defaults to active branch if None.", default=None)),
    whitelist=(Optional[List[str]], Field(description='File extensions or paths to include. Defaults to all files if None. Example: ["*.md", "*.java"]', default=None)),
    blacklist=(Optional[List[str]], Field(description='File extensions or paths to exclude. Defaults to no exclusions if None. Example: ["*.md", "*.java"]', default=None)),

)

RemoveIndexParams = create_model(
    "RemoveIndexParams",
    index_name=(Optional[str], Field(description="Optional index name (max 7 characters)", default="", max_length=7)),
)

BaseSearchParams = create_model(
    "BaseSearchParams",
    query=(str, Field(description="Query text to search in the index")),
    index_name=(Optional[str], Field(
        description="Optional index name (max 7 characters). Leave empty to search across all datasets",
        default="", max_length=7)),
    filter=(Optional[dict], Field(
        description="Filter to apply to the search results. Can be a dictionary or a JSON string.",
        default={},
        examples=["{\"key\": \"value\"}", "{\"status\": \"active\"}"]
    )),
    cut_off=(Optional[float], Field(description="Cut-off score for search results", default=0.5, ge=0, le=1)),
    search_top=(Optional[int], Field(description="Number of top results to return", default=10, ge=0)),
    full_text_search=(Optional[Dict[str, Any]], Field(
        description="Full text search parameters. Can be a dictionary with search options.",
        default=None
    )),
    extended_search=(Optional[List[str]], Field(
        description="List of additional fields to include in the search results.",
        default=None
    )),
    reranker=(Optional[dict], Field(
        description="Reranker configuration. Can be a dictionary with reranking parameters.",
        default={}
    )),
    reranking_config=(Optional[Dict[str, Dict[str, Any]]], Field(
        description="Reranking configuration. Can be a dictionary with reranking settings.",
        default=None
    )),
)

BaseStepbackSearchParams = create_model(
    "BaseStepbackSearchParams",
    query=(str, Field(description="Query text to search in the index")),
    index_name=(Optional[str], Field(description="Optional index name (max 7 characters)", default="", max_length=7)),
    messages=(Optional[List], Field(description="Chat messages for stepback search context", default=[])),
    filter=(Optional[dict], Field(
        description="Filter to apply to the search results. Can be a dictionary or a JSON string.",
        default={},
        examples=["{\"key\": \"value\"}", "{\"status\": \"active\"}"]
    )),
    cut_off=(Optional[float], Field(description="Cut-off score for search results", default=0.5, ge=0, le=1)),
    search_top=(Optional[int], Field(description="Number of top results to return", default=10, ge=0)),
    full_text_search=(Optional[Dict[str, Any]], Field(
        description="Full text search parameters. Can be a dictionary with search options.",
        default=None
    )),
    extended_search=(Optional[List[str]], Field(
        description="List of additional fields to include in the search results.",
        default=None
    )),
    reranker=(Optional[dict], Field(
        description="Reranker configuration. Can be a dictionary with reranking parameters.",
        default={}
    )),
    reranking_config=(Optional[Dict[str, Dict[str, Any]]], Field(
        description="Reranking configuration. Can be a dictionary with reranking settings.",
        default=None
    )),

)

BaseIndexDataParams = create_model(
    "indexData",
    __base__=BaseIndexParams,
    clean_index=(Optional[bool], Field(default=False,
                       description="Optional flag to enforce clean existing index before indexing new data")),
    progress_step=(Optional[int], Field(default=5, ge=0, le=100,
                         description="Optional step size for progress reporting during indexing")),
    chunking_tool=(Literal[None,'markdown', 'statistical', 'proposal'], Field(description="Name of chunking tool", default=None)),
    chunking_config=(Optional[dict], Field(description="Chunking tool configuration", default_factory=dict)),
)

# File Operations Schema Models
ReadFileInput = create_model(
    "ReadFileInput",
    file_path=(str, Field(description="Path to the file to read")),
    branch=(Optional[str], Field(description="Branch name. If None, uses active branch.", default=None)),
    offset=(Optional[int], Field(description="Starting line number (1-indexed, inclusive). Read from this line onwards.", default=None, ge=1)),
    limit=(Optional[int], Field(description="Number of lines to read from offset. If None, reads to end.", default=None, ge=1)),
    head=(Optional[int], Field(description="Read only the first N lines. Alternative to offset/limit.", default=None, ge=1)),
    tail=(Optional[int], Field(description="Read only the last N lines. Alternative to offset/limit.", default=None, ge=1)),
)

ReadFileChunkInput = create_model(
    "ReadFileChunkInput",
    file_path=(str, Field(description="Path to the file to read")),
    branch=(Optional[str], Field(description="Branch name. If None, uses active branch.", default=None)),
    start_line=(int, Field(description="Starting line number (1-indexed, inclusive)", ge=1)),
    end_line=(Optional[int], Field(description="Ending line number (1-indexed, inclusive). If None, reads to end.", default=None, ge=1)),
)

ReadMultipleFilesInput = create_model(
    "ReadMultipleFilesInput",
    file_paths=(List[str], Field(description="List of file paths to read", min_length=1)),
    branch=(Optional[str], Field(description="Branch name. If None, uses active branch.", default=None)),
    offset=(Optional[int], Field(description="Starting line number for all files (1-indexed)", default=None, ge=1)),
    limit=(Optional[int], Field(description="Number of lines to read from offset for all files", default=None, ge=1)),
)

EditFileInput = create_model(
    "EditFileInput",
    file_path=(str, Field(description="Path to the file to edit. Must be a text file (markdown, txt, csv, json, xml, html, yaml, etc.)")),
    file_query=(str, Field(description="""Edit instructions with OLD/NEW markers. Format:
OLD <<<<
old content to replace
>>>> OLD
NEW <<<<
new content
>>>> NEW

Multiple OLD/NEW pairs can be provided for multiple edits.""")),
    branch=(Optional[str], Field(description="Branch name. If None, uses active branch.", default=None)),
    commit_message=(Optional[str], Field(description="Commit message for the change (VCS toolkits only)", default=None)),
)

SearchFileInput = create_model(
    "SearchFileInput",
    file_path=(str, Field(description="Path to the file to search")),
    pattern=(str, Field(description="Search pattern. Treated as regex by default unless is_regex=False.")),
    branch=(Optional[str], Field(description="Branch name. If None, uses active branch.", default=None)),
    is_regex=(bool, Field(description="Whether pattern is a regex. Default is True for flexible matching.", default=True)),
    context_lines=(int, Field(description="Number of lines before/after match to include for context", default=2, ge=0)),
)


class BaseToolApiWrapper(BaseModel):
    
    # Optional RunnableConfig for CLI/standalone usage (allows dispatch_custom_event to work)
    _runnable_config: Optional[Dict[str, Any]] = None
    # toolkit id propagated from backend
    toolkit_id: int = 0
    def get_available_tools(self):
        raise NotImplementedError("Subclasses should implement this method")

    def set_runnable_config(self, config: Optional[Dict[str, Any]]) -> None:
        """
        Set the RunnableConfig for dispatching custom events.
        
        This is required when running outside of a LangChain agent context
        (e.g., from CLI). Without a config containing a run_id, 
        dispatch_custom_event will fail with "Unable to dispatch an adhoc event 
        without a parent run id".
        
        Args:
            config: A RunnableConfig dict with at least {'run_id': uuid}
        """
        self._runnable_config = config

    def _log_tool_event(self, message: str, tool_name: str = None, config: Optional[Dict[str, Any]] = None):
        """Log data and dispatch custom event for the tool.
        
        Args:
            message: The message to log
            tool_name: Name of the tool (defaults to 'tool_progress')
            config: Optional RunnableConfig. If not provided, uses self._runnable_config.
                   Required when running outside a LangChain agent context.
        """

        try:
            from langchain_core.callbacks import dispatch_custom_event

            if tool_name is None:
                tool_name = 'tool_progress'

            logger.info(message)
            
            # Use provided config, fall back to instance config
            effective_config = config or self._runnable_config
            
            dispatch_custom_event(
                name="thinking_step",
                data={
                    "message": message,
                    "tool_name": tool_name,
                    "toolkit": self.__class__.__name__,
                },
                config=effective_config,
            )
        except Exception as e:
            logger.warning(f"Failed to dispatch progress event: {str(e)}")


    def run(self, mode: str, *args: Any, **kwargs: Any):
        # Mode is now the clean tool name (no prefix to remove)
        for tool in self.get_available_tools():
            if tool["name"] == mode:
                try:
                    execution = tool["ref"](*args, **kwargs)
                    # if not isinstance(execution, str):
                    #     execution = str(execution)
                    return execution
                except Exception as e:
                    # Re-raise McpAuthorizationRequired directly without wrapping
                    from alita_sdk.runtime.utils.mcp_oauth import McpAuthorizationRequired
                    if isinstance(e, McpAuthorizationRequired):
                        raise
                    
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

    doctype: str = "document"

    llm: Any = None
    connection_string: Optional[SecretStr] = None
    collection_name: Optional[str] = None
    embedding_model: Optional[str] = "HuggingFaceEmbeddings"
    embedding_model_params: Optional[Dict[str, Any]] = {"model_name": "sentence-transformers/all-MiniLM-L6-v2"}
    vectorstore_type: Optional[str] = "PGVector"
    _vector_store: Optional[Any] = None
    _embedding: Optional[Any] = None
    alita: Any = None # Elitea client, if available

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._adapter = VectorStoreAdapterFactory.create_adapter(self.vectorstore_type)
        if self.alita and self.embedding_model:
            self._embedding = self.alita.get_embeddings(self.embedding_model)

    def _index_tool_params(self, **kwargs) -> dict[str, tuple[type, Field]]:
        """
        Returns a list of fields for index_data args schema.
        NOTE: override this method in subclasses to provide specific parameters for certain toolkit.
        """
        return {}

    def _get_dependencies_chunker(self, document: Optional[Document] = None):
        return markdown_chunker

    def _get_dependencies_chunker_config(self, document: Optional[Document] = None):
        return {'embedding': self._embedding, 'llm': self.llm}

    def _base_loader(self, **kwargs) -> Generator[Document, None, None]:
        """ Loads documents from a source, processes them,
        and returns a list of Document objects with base metadata: id and created_on."""
        pass

    def _process_document(self, base_document: Document) -> Generator[Document, None, None]:
        """ Process an existing base document to extract relevant metadata for full document preparation.
        Used for late processing of documents after we ensure that the document has to be indexed to avoid
        time-consuming operations for documents which might be useless.

        Args:
            document (Document): The base document to process.

        Returns:
            Document: The processed document with metadata."""
        pass

    def get_index_data_tool(self):
        return {
            "name": "index_data",
            "ref": self.index_data,
            "description": "Loads data to index.",
            "args_schema": create_model(
                "IndexData",
                __base__=BaseIndexDataParams,
                **self._index_tool_params() if self._index_tool_params() else {}
            )
        }

    def index_data(self, **kwargs):
        from alita_sdk.tools.chunkers import __confluence_chunkers__ as chunkers, __confluence_models__ as models
        docs = self._base_loader(**kwargs)
        chunking_tool = kwargs.get("chunking_tool")
        if chunking_tool:
            # Resolve chunker from the provided chunking_tool name
            base_chunker = chunkers.get(chunking_tool)
            # Resolve chunking configuration
            base_chunking_config = kwargs.get("chunking_config", {})
            config_model = models.get(chunking_tool)
            # Set required fields that should come from the instance (and Fallback for chunkers without models)
            base_chunking_config['embedding'] = self._embedding
            base_chunking_config['llm'] = self.llm
            #
            if config_model:
                try:
                    # Validate the configuration using the appropriate Pydantic model
                    validated_config = config_model(**base_chunking_config)
                    base_chunking_config = validated_config.model_dump()
                except Exception as e:
                    logger.error(f"Invalid chunking configuration for {chunking_tool}: {e}")
                    raise ToolException(f"Invalid chunking configuration: {e}")
            #
            docs = base_chunker(file_content_generator=docs, config=base_chunking_config)
        #
        index_name = kwargs.get("index_name")
        progress_step = kwargs.get("progress_step")
        clean_index = kwargs.get("clean_index")
        vs = self._init_vector_store()
        #
        return vs.index_documents(docs, index_name=index_name, progress_step=progress_step, clean_index=clean_index)

    def _process_documents(self, documents: List[Document]) -> Generator[Document, None, None]:
        """
        Process a list of base documents to extract relevant metadata for full document preparation.
        Used for late processing of documents after we ensure that the documents have to be indexed to avoid
        time-consuming operations for documents which might be useless.
        This function passed to index_documents method of vector store and called after _reduce_duplicates method.

        Args:
            documents (List[Document]): The base documents to process.

        Returns:
            Generator[Document, None, None]: A generator yielding processed documents with metadata.
        """
        total_docs = len(documents)
        self._log_tool_event(
            message=f"Preparing a base documents for indexing. Total documents: {total_docs}",
            tool_name="_process_documents"
        )
        processed_count = 0
        for idx, doc in enumerate(documents, 1):
            # Filter documents to process only those that either:
            # - do not have a 'chunk_id' in their metadata, or
            # - have 'chunk_id' explicitly set to 1.
            # This prevents processing of irrelevant or duplicate chunks, improving efficiency.
            chunk_id = doc.metadata.get("chunk_id")
            if chunk_id is None or chunk_id == 1:
                processed_docs = self._process_document(doc)
                if processed_docs:  # Only proceed if the list is not empty
                    for processed_doc in processed_docs:
                        # map processed document (child) to the original document (parent)
                        processed_doc.metadata[IndexerKeywords.PARENT.value] = doc.metadata.get('id', None)
                        if chunker := self._get_dependencies_chunker(processed_doc):
                            yield from chunker(
                                file_content_generator=iter([processed_doc]),
                                config=self._get_dependencies_chunker_config()
                            )
                        else:
                            yield processed_doc
                processed_count += 1
                if processed_count % 5 == 0 or processed_count == total_docs:
                    self._log_tool_event(
                        message=f"Prepared {processed_count} out of {total_docs} documents for indexing.",
                        tool_name="_process_documents"
                    )


    # TODO: init store once and re-use the instance
    def _init_vector_store(self):
        """Initializes the vector store wrapper with the provided parameters."""
        try:
            from alita_sdk.runtime.tools.vectorstore import VectorStoreWrapper
        except ImportError:
            from alita_sdk.runtime.tools.vectorstore import VectorStoreWrapper

        if not self._vector_store:
            connection_string = self.connection_string.get_secret_value() if self.connection_string else None
            vectorstore_params = self._adapter.get_vectorstore_params(self.collection_name, connection_string)
            self._vector_store = VectorStoreWrapper(
                llm=self.llm,
                vectorstore_type=self.vectorstore_type,
                embedding_model=self.embedding_model,
                embedding_model_params=self.embedding_model_params,
                vectorstore_params=vectorstore_params,
                embeddings=self._embedding,
                process_document_func=self._process_documents,
            )
        return self._vector_store

    def remove_index(self, index_name: str = ""):
        """Cleans the indexed data in the collection."""
        self._init_vector_store()._clean_collection(index_name=index_name)
        return (f"Collection '{index_name}' has been removed from the vector store.\n"
                f"Available collections: {self.list_collections()}")

    def list_collections(self):
        """Lists all collections in the vector store."""
        vectorstore_wrapper = self._init_vector_store()
        return vectorstore_wrapper.list_collections()

    def _build_collection_filter(self, filter: dict | str, index_name: str = "") -> dict:
        """Builds a filter for the collection based on the provided suffix."""

        filter = filter if isinstance(filter, dict) else json.loads(filter)
        if index_name:
            filter.update({"collection": {
                "$eq": index_name.strip()
            }})
        return filter

    def search_index(self,
                     query: str,
                     index_name: str = "",
                     filter: dict | str = {}, cut_off: float = 0.5,
                     search_top: int = 10, reranker: dict = {},
                     full_text_search: Optional[Dict[str, Any]] = None,
                     reranking_config: Optional[Dict[str, Dict[str, Any]]] = None,
                     extended_search: Optional[List[str]] = None,
                     **kwargs):
        """ Searches indexed documents in the vector store."""
        vectorstore = self._init_vector_store()
        filter = self._build_collection_filter(filter, index_name)
        found_docs = vectorstore.search_documents(
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
        return found_docs if found_docs else f"No documents found by query '{query}' and filter '{filter}'"

    def stepback_search_index(self,
                     query: str,
                     messages: List[Dict[str, Any]] = [],
                     index_name: str = "",
                     filter: dict | str = {}, cut_off: float = 0.5,
                     search_top: int = 10, reranker: dict = {},
                     full_text_search: Optional[Dict[str, Any]] = None,
                     reranking_config: Optional[Dict[str, Dict[str, Any]]] = None,
                     extended_search: Optional[List[str]] = None,
                     **kwargs):
        """ Searches indexed documents in the vector store."""

        filter = self._build_collection_filter(filter, index_name)
        vectorstore = self._init_vector_store()
        found_docs = vectorstore.stepback_search(
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
        return found_docs if found_docs else f"No documents found by query '{query}' and filter '{filter}'"

    def stepback_summary_index(self,
                     query: str,
                     messages: List[Dict[str, Any]] = [],
                     index_name: str = "",
                     filter: dict | str = {}, cut_off: float = 0.5,
                     search_top: int = 10, reranker: dict = {},
                     full_text_search: Optional[Dict[str, Any]] = None,
                     reranking_config: Optional[Dict[str, Dict[str, Any]]] = None,
                     extended_search: Optional[List[str]] = None,
                     **kwargs):
        """ Generates a summary of indexed documents using stepback technique."""
        vectorstore = self._init_vector_store()
        filter = self._build_collection_filter(filter, index_name)

        found_docs = vectorstore.stepback_summary(
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
        return found_docs if found_docs else f"No documents found by query '{query}' and filter '{filter}'"

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
            },
            {
                "name": "remove_index",
                "mode": "remove_index",
                "ref": self.remove_index,
                "description": self.remove_index.__doc__,
                "args_schema": RemoveIndexParams
            },
            {
                "name": "list_collections",
                "mode": "list_collections",
                "ref": self.list_collections,
                "description": self.list_collections.__doc__,
                "args_schema": create_model("ListCollectionsParams")  # No parameters
            },

        ]


class BaseCodeToolApiWrapper(BaseVectorStoreToolApiWrapper):

    doctype: Optional[str] = 'code'

    def _get_files(self):
        raise NotImplementedError("Subclasses should implement this method")

    def _read_file(
        self, 
        file_path: str, 
        branch: str = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
        head: Optional[int] = None,
        tail: Optional[int] = None,
        **kwargs  # Allow subclasses to have additional parameters
    ) -> str:
        """
        Read file content with optional partial read support.
        
        Subclasses should implement this method. If they don't support partial reads,
        they can accept **kwargs and ignore offset/limit/head/tail parameters - the base 
        class high-level methods will apply slicing client-side.
        
        Args:
            file_path: Path to the file
            branch: Branch name (None for active branch)
            offset: Starting line number (1-indexed)
            limit: Number of lines to read from offset
            head: Read only first N lines
            tail: Read only last N lines
            **kwargs: Additional toolkit-specific parameters (e.g., repo_name for GitHub)
            
        Returns:
            File content as string
        """
        raise NotImplementedError("Subclasses should implement this method")
    
    def _write_file(
        self,
        file_path: str,
        content: str,
        branch: str = None,
        commit_message: str = None
    ) -> str:
        """
        Write content to a file.
        
        Subclasses should implement this method to enable edit_file functionality.
        For VCS toolkits, this may involve creating or updating files with commits.
        
        Args:
            file_path: Path to the file
            content: New file content
            branch: Branch name (None for active branch)
            commit_message: Commit message (VCS toolkits only)
            
        Returns:
            Success message
        """
        raise NotImplementedError("Subclasses should implement _write_file to enable editing")

    def _file_commit_hash(self, file_path: str, branch: str):
        pass
    
    def read_file_chunk(
        self,
        file_path: str,
        start_line: int,
        end_line: Optional[int] = None,
        branch: str = None
    ) -> str:
        """
        Read a specific range of lines from a file.
        
        Args:
            file_path: Path to the file
            start_line: Starting line number (1-indexed, inclusive)
            end_line: Ending line number (1-indexed, inclusive). If None, reads to end.
            branch: Branch name (None for active branch)
            
        Returns:
            File content for the specified line range
        """
        from .utils.text_operations import apply_line_slice
        
        # Calculate offset and limit from start_line and end_line
        offset = start_line
        limit = (end_line - start_line + 1) if end_line is not None else None
        
        # Read the file with offset/limit
        content = self._read_file(file_path, branch, offset=offset, limit=limit)
        
        # Apply client-side slicing if toolkit doesn't support partial reads
        # (toolkit's _read_file will return full content if it ignores offset/limit)
        return apply_line_slice(content, offset=offset, limit=limit)
    
    def read_multiple_files(
        self,
        file_paths: List[str],
        branch: str = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None
    ) -> Dict[str, str]:
        """
        Read multiple files in batch.
        
        Args:
            file_paths: List of file paths to read
            branch: Branch name (None for active branch)
            offset: Starting line number for all files (1-indexed)
            limit: Number of lines to read from offset for all files
            
        Returns:
            Dictionary mapping file paths to their content (or error messages)
        """
        results = {}
        
        for file_path in file_paths:
            try:
                content = self._read_file(
                    file_path, 
                    branch, 
                    offset=offset, 
                    limit=limit
                )
                results[file_path] = content
            except Exception as e:
                results[file_path] = f"Error reading file: {str(e)}"
                logger.error(f"Failed to read {file_path}: {e}")
        
        return results
    
    def search_file(
        self,
        file_path: str,
        pattern: str,
        branch: str = None,
        is_regex: bool = True,
        context_lines: int = 2
    ) -> str:
        """
        Search for pattern in file content with context.
        
        Args:
            file_path: Path to the file
            pattern: Search pattern (regex if is_regex=True, else literal)
            branch: Branch name (None for active branch)
            is_regex: Whether pattern is regex (default True)
            context_lines: Lines of context before/after matches (default 2)
            
        Returns:
            Formatted string with search results and context
        """
        from .utils.text_operations import search_in_content
        
        # Read full file content
        content = self._read_file(file_path, branch)
        
        # Search for pattern
        matches = search_in_content(content, pattern, is_regex, context_lines)
        
        if not matches:
            return f"No matches found for pattern '{pattern}' in {file_path}"
        
        # Format results
        result_lines = [f"Found {len(matches)} match(es) for pattern '{pattern}' in {file_path}:\n"]
        
        for i, match in enumerate(matches, 1):
            result_lines.append(f"\n--- Match {i} at line {match['line_number']} ---")
            
            # Context before
            if match['context_before']:
                for line in match['context_before']:
                    result_lines.append(f"  {line}")
            
            # Matching line (highlighted)
            result_lines.append(f"> {match['line_content']}")
            
            # Context after
            if match['context_after']:
                for line in match['context_after']:
                    result_lines.append(f"  {line}")
        
        return "\n".join(result_lines)
    
    def edit_file(
        self,
        file_path: str,
        file_query: str,
        branch: str = None,
        commit_message: str = None
    ) -> str:
        """
        Edit file using OLD/NEW markers for precise replacements.
        
        Only works with text files (markdown, txt, csv, json, xml, html, yaml, code files).
        
        Args:
            file_path: Path to the file to edit
            file_query: Edit instructions with OLD/NEW markers
            branch: Branch name (None for active branch)
            commit_message: Commit message (VCS toolkits only)
            
        Returns:
            Success message or error
            
        Raises:
            ToolException: If file is not text-editable or edit fails
        """
        from .utils.text_operations import parse_old_new_markers, is_text_editable
        from langchain_core.callbacks import dispatch_custom_event
        
        # Validate file is text-editable
        if not is_text_editable(file_path):
            raise ToolException(
                f"Cannot edit binary/document file '{file_path}'. "
                f"Supported text formats: markdown, txt, csv, json, xml, html, yaml, code files."
            )
        
        # Parse OLD/NEW markers
        edits = parse_old_new_markers(file_query)
        if not edits:
            raise ToolException(
                "No OLD/NEW marker pairs found in file_query. "
                "Format: OLD <<<< old text >>>> OLD  NEW <<<< new text >>>> NEW"
            )
        
        # Read current file content
        try:
            current_content = self._read_file(file_path, branch)
        except Exception as e:
            raise ToolException(f"Failed to read file {file_path}: {e}")
        
        # Apply all edits
        updated_content = current_content
        for old_text, new_text in edits:
            if not old_text.strip():
                continue
            
            if old_text not in updated_content:
                logger.warning(
                    f"Old content not found in {file_path}. "
                    f"Looking for: {old_text[:100]}..."
                )
                continue
            
            updated_content = updated_content.replace(old_text, new_text)
        
        # Check if any changes were made
        if current_content == updated_content:
            return (
                f"No changes made to {file_path}. "
                "Old content was not found or is empty. "
                "Use read_file or search_file to verify current content."
            )
        
        # Write updated content
        try:
            result = self._write_file(file_path, updated_content, branch, commit_message)
        except NotImplementedError:
            raise ToolException(
                f"Editing not supported for this toolkit. "
                f"The _write_file method is not implemented."
            )
        except Exception as e:
            raise ToolException(f"Failed to write file {file_path}: {e}")
        
        # Dispatch file modification event
        try:
            dispatch_custom_event("file_modified", {
                "message": f"File '{file_path}' edited successfully",
                "filename": file_path,
                "tool_name": "edit_file",
                "toolkit": self.__class__.__name__,
                "operation_type": "modify",
                "edits_applied": len(edits)
            })
        except Exception as e:
            logger.warning(f"Failed to dispatch file_modified event: {e}")
        
        return result

    def __handle_get_files(self, path: str, branch: str):
        """
        Handles the retrieval of files from a specific path and branch.
        This method should be implemented in subclasses to provide the actual file retrieval logic.
        """
        _files = self._get_files(path=path, branch=branch)
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

    def __get_branch(self, branch):
       return (branch or getattr(self, 'active_branch', None)
               or getattr(self, '_active_branch', None) or getattr(self, 'branch', None))

    def loader(self,
               branch: Optional[str] = None,
               whitelist: Optional[List[str]] = None,
               blacklist: Optional[List[str]] = None,
               chunked: bool = True) -> Generator[Document, None, None]:
        """
        Generates Documents from files in a branch, respecting whitelist and blacklist patterns.

        Parameters:
        - branch (Optional[str]): Branch for listing files. Defaults to the current branch if None.
        - whitelist (Optional[List[str]]): File extensions or paths to include. Defaults to all files if None.
        - blacklist (Optional[List[str]]): File extensions or paths to exclude. Defaults to no exclusions if None.
        - chunked (bool): If True (default), applies universal chunker based on file type.
                         If False, returns raw Documents without chunking.

        Returns:
        - generator: Yields Documents from files matching the whitelist but not the blacklist.

        Example:
        # Use 'feature-branch', include '.py' files, exclude 'test_' files
        for doc in loader(branch='feature-branch', whitelist=['*.py'], blacklist=['*test_*']):
            print(doc.page_content)

        Notes:
        - Whitelist and blacklist use Unix shell-style wildcards.
        - Files must match the whitelist and not the blacklist to be included.
        - When chunked=True:
          - .md files → markdown chunker (header-based splitting)
          - .py/.js/.ts/etc → code parser (TreeSitter-based)
          - .json files → JSON chunker
          - other files → default text chunker
        """
        from langchain_core.documents import Document
        import hashlib

        _files = self.__handle_get_files("", self.__get_branch(branch))
        self._log_tool_event(message="Listing files in branch", tool_name="loader")
        logger.info(f"Files in branch: {_files}")

        def is_whitelisted(file_path: str) -> bool:
            if whitelist:
                return (any(fnmatch.fnmatch(file_path, pattern) for pattern in whitelist)
                        or any(file_path.endswith(f'.{pattern}') for pattern in whitelist))
            return True

        def is_blacklisted(file_path: str) -> bool:
            if blacklist:
                return (any(fnmatch.fnmatch(file_path, pattern) for pattern in blacklist)
                        or any(file_path.endswith(f'.{pattern}') for pattern in blacklist))
            return False

        def raw_document_generator() -> Generator[Document, None, None]:
            """Yields raw Documents without chunking."""
            self._log_tool_event(message="Reading the files", tool_name="loader")
            total_files = len(_files)
            processed = 0
            
            for idx, file in enumerate(_files, 1):
                if is_whitelisted(file) and not is_blacklisted(file):
                    try:
                        file_content = self._read_file(file, self.__get_branch(branch))
                    except Exception as e:
                        logger.error(f"Failed to read file {file}: {e}")
                        continue
                    
                    if not file_content:
                        continue
                    
                    # Hash the file content for uniqueness tracking
                    file_hash = hashlib.sha256(file_content.encode("utf-8")).hexdigest()
                    processed += 1
                    
                    yield Document(
                        page_content=file_content,
                        metadata={
                            'file_path': file,
                            'file_name': file,
                            'source': file,
                            'commit_hash': file_hash,
                        }
                    )
                
                if idx % 10 == 0 or idx == total_files:
                    self._log_tool_event(
                        message=f"{idx} out of {total_files} files checked, {processed} matched",
                        tool_name="loader"
                    )
            
            self._log_tool_event(message=f"{processed} files loaded", tool_name="loader")

        if not chunked:
            # Return raw documents without chunking
            return raw_document_generator()
        
        # Apply universal chunker based on file type
        from .chunkers.universal_chunker import universal_chunker
        return universal_chunker(raw_document_generator())
    
    def index_data(self,
                   index_name: str,
                   branch: Optional[str] = None,
                   whitelist: Optional[List[str]] = None,
                   blacklist: Optional[List[str]] = None,
                   **kwargs) -> str:
        """Index repository files in the vector store using code parsing."""
        
        documents = self.loader(
            branch=branch,
            whitelist=whitelist,
            blacklist=blacklist
        )
        vectorstore = self._init_vector_store()
        clean_index = kwargs.get('clean_index', False)
        return vectorstore.index_documents(documents, index_name=index_name,
                                           clean_index=clean_index, is_code=True,
                                           progress_step=kwargs.get('progress_step', 5))

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

def extend_with_vector_tools(method):
    def wrapper(self, *args, **kwargs):
        tools = method(self, *args, **kwargs)
        tools.extend(self._get_vector_search_tools())        
        #
        if isinstance(self, BaseVectorStoreToolApiWrapper):
            tools.append(self.get_index_data_tool())
        #
        return tools

    return wrapper


def extend_with_file_operations(method):
    """
    Decorator to automatically add file operation tools to toolkits that implement
    _read_file and _write_file methods.
    
    Adds:
    - read_file_chunk: Read specific line ranges
    - read_multiple_files: Batch read files
    - search_file: Search for patterns in files
    - edit_file: Edit files using OLD/NEW markers
    """
    def wrapper(self, *args, **kwargs):
        tools = method(self, *args, **kwargs)
        
        # Only add file operations if toolkit has implemented the required methods
        # Check for both _read_file and _write_file methods
        has_file_ops = (hasattr(self, '_read_file') and callable(getattr(self, '_read_file')) and
                        hasattr(self, '_write_file') and callable(getattr(self, '_write_file')))
        
        if has_file_ops:
            # Import schemas from elitea_base
            from . import elitea_base
            
            file_operation_tools = [
                {
                    "name": "read_file_chunk",
                    "mode": "read_file_chunk",
                    "ref": self.read_file_chunk,
                    "description": self.read_file_chunk.__doc__,
                    "args_schema": elitea_base.ReadFileChunkInput
                },
                {
                    "name": "read_multiple_files",
                    "mode": "read_multiple_files",
                    "ref": self.read_multiple_files,
                    "description": self.read_multiple_files.__doc__,
                    "args_schema": elitea_base.ReadMultipleFilesInput
                },
                {
                    "name": "search_file",
                    "mode": "search_file",
                    "ref": self.search_file,
                    "description": self.search_file.__doc__,
                    "args_schema": elitea_base.SearchFileInput
                },
                {
                    "name": "edit_file",
                    "mode": "edit_file",
                    "ref": self.edit_file,
                    "description": self.edit_file.__doc__,
                    "args_schema": elitea_base.EditFileInput
                },
            ]
            
            tools.extend(file_operation_tools)
        
        return tools
    
    return wrapper


def filter_missconfigured_index_tools(method):
    def wrapper(self, *args, **kwargs):
        toolkit = method(self, *args, **kwargs)

        # Validate index tools misconfiguration and exclude them if necessary
        is_index_toolkit = any(tool.name in INDEX_TOOL_NAMES for tool in toolkit.tools)
        is_index_configuration_missing = not (kwargs.get('embedding_model')
                                              and kwargs.get('pgvector_configuration'))

        if is_index_toolkit and is_index_configuration_missing:
            toolkit.tools = [tool for tool in toolkit.tools if tool.name not in INDEX_TOOL_NAMES]

        return toolkit

    return wrapper
