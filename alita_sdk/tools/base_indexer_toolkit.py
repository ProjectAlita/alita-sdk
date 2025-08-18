import json
import logging
from typing import Any, Optional, List, Literal, Dict, Generator

from langchain_core.documents import Document
from pydantic import create_model, Field, SecretStr

# from alita_sdk.runtime.langchain.interfaces.llm_processor import get_embeddings
from .chunkers import markdown_chunker
from .utils.content_parser import process_content_by_type
from .vector_adapters.VectorStoreAdapter import VectorStoreAdapterFactory
from ..runtime.tools.vectorstore_base import VectorStoreWrapperBase
from ..runtime.utils.utils import IndexerKeywords

logger = logging.getLogger(__name__)

# Base Vector Store Schema Models
BaseIndexParams = create_model(
    "BaseIndexParams",
    collection_suffix=(str, Field(description="Suffix for collection name (max 7 characters) used to separate datasets", min_length=1, max_length=7)),
    vectorstore_type=(Optional[str], Field(description="Vectorstore type (Chroma, PGVector, Elastic, etc.)", default="PGVector")),
)

RemoveIndexParams = create_model(
    "RemoveIndexParams",
    collection_suffix=(Optional[str], Field(description="Optional suffix for collection name (max 7 characters)", default="", max_length=7)),
)

BaseSearchParams = create_model(
    "BaseSearchParams",
    query=(str, Field(description="Query text to search in the index")),
    collection_suffix=(Optional[str], Field(
        description="Optional suffix for collection name (max 7 characters). Leave empty to search across all datasets",
        default="", max_length=7)),
    vectorstore_type=(Optional[str], Field(description="Vectorstore type (Chroma, PGVector, Elastic, etc.)", default="PGVector")),
    filter=(Optional[dict | str], Field(
        description="Filter to apply to the search results. Can be a dictionary or a JSON string.",
        default={},
        examples=["{\"key\": \"value\"}", "{\"status\": \"active\"}"]
    )),
    cut_off=(Optional[float], Field(description="Cut-off score for search results", default=0.5)),
    search_top=(Optional[int], Field(description="Number of top results to return", default=10)),
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

BaseIndexDataParams = create_model(
    "indexData",
    __base__=BaseIndexParams,
    progress_step=(Optional[int], Field(default=10, ge=0, le=100,
                         description="Optional step size for progress reporting during indexing")),
    clean_index=(Optional[bool], Field(default=False,
                       description="Optional flag to enforce clean existing index before indexing new data")),
    chunking_tool=(Literal[None,'markdown', 'statistical', 'proposal'], Field(description="Name of chunking tool", default=None)),
    chunking_config=(Optional[dict], Field(description="Chunking tool configuration", default_factory=dict)),
)


class BaseIndexerToolkit(VectorStoreWrapperBase):
    """Base class for tool API wrappers that support vector store functionality."""

    doctype: str = "document"

    llm: Any = None
    connection_string: Optional[SecretStr] = None
    collection_name: Optional[str] = None
    embedding_model: Optional[str] = "HuggingFaceEmbeddings"
    embedding_model_params: Optional[Dict[str, Any]] = {"model_name": "sentence-transformers/all-MiniLM-L6-v2"}
    vectorstore_type: Optional[str] = "PGVector"
    _embedding: Optional[Any] = None
    alita: Any = None # Elitea client, if available

    def __init__(self, **kwargs):
        conn = kwargs.get('connection_string', None)
        connection_string = conn.get_secret_value() if isinstance(conn, SecretStr) else conn
        collection_name = kwargs.get('collection_name')
        
        # if 'embedding_model' not in kwargs:
        kwargs['embedding_model'] = 'HuggingFaceEmbeddings'
        if 'embedding_model_params' not in kwargs:
            kwargs['embedding_model_params'] = {"model_name": "sentence-transformers/all-MiniLM-L6-v2"}
        if 'vectorstore_type' not in kwargs:
            kwargs['vectorstore_type'] = 'PGVector'
        vectorstore_type = kwargs.get('vectorstore_type')
        kwargs['vectorstore_params'] = VectorStoreAdapterFactory.create_adapter(vectorstore_type).get_vectorstore_params(collection_name, connection_string)
        kwargs['_embedding'] = kwargs.get('alita').get_embeddings(kwargs.get('embedding_model'))
        super().__init__(**kwargs)

    def _index_tool_params(self, **kwargs) -> dict[str, tuple[type, Field]]:
        """
        Returns a list of fields for index_data args schema.
        NOTE: override this method in subclasses to provide specific parameters for certain toolkit.
        """
        return {}

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

    def index_data(self, **kwargs):
        collection_suffix = kwargs.get("collection_suffix")
        progress_step = kwargs.get("progress_step")
        clean_index = kwargs.get("clean_index")
        chunking_tool = kwargs.get("chunking_tool")
        chunking_config = kwargs.get("chunking_config")
        #
        if clean_index:
            self._clean_index()
        #
        documents = self._base_loader(**kwargs)
        documents = self._reduce_duplicates(documents, collection_suffix)
        documents = self._extend_data(documents) # update content of not-reduced base document if needed (for sharepoint and similar)
        documents = self._collect_dependencies(documents) # collect dependencies for base documents
        documents = self._apply_loaders_chunkers(documents, chunking_tool, chunking_config)
        #
        return self._save_index(list(documents), collection_suffix=collection_suffix, progress_step=progress_step)
    
    def _apply_loaders_chunkers(self, documents: Generator[Document, None, None], chunking_tool: str=None, chunking_config=None) -> Generator[Document, None, None]:
        from alita_sdk.tools.chunkers import __confluence_chunkers__ as chunkers, __confluence_models__ as models

        if chunking_config is None:
            chunking_config = {}
        chunking_config['embedding'] = self._embedding
        chunking_config['llm'] = self.llm
            
        for document in documents:
            if content_type := document.metadata.get('loader_content_type', None):
                # apply parsing based on content type and chunk if chunker was applied to parent doc
                yield from process_content_by_type(
                    document=document,
                    extension_source=content_type, llm=self.llm, chunking_config=chunking_config)
            elif chunking_tool:
                # apply default chunker from toolkit config. No parsing.
                chunker = chunkers.get(chunking_tool)
                yield from chunker(file_content_generator=iter([document]), config=chunking_config)
            else:
                # return as is if neither chunker or content typa are specified
                yield document
    
    def _extend_data(self, documents: Generator[Document, None, None]):
        yield from documents

    def _collect_dependencies(self, documents: Generator[Document, None, None]):
        for document in documents:
            dependencies = self._process_document(document)
            yield document
            for dep in dependencies:
                dep.metadata[IndexerKeywords.PARENT.value] = document.metadata.get('id', None)
                yield dep
    
    def _content_loader(self):
        pass

    def _reduce_duplicates(
            self,
            documents: Generator[Any, None, None],
            collection_suffix: str,
            log_msg: str = "Verification of documents to index started"
    ) -> Generator[Document, None, None]:
        """Generic duplicate reduction logic for documents."""
        self._log_data(log_msg, tool_name="index_documents")
        indexed_data = self._get_indexed_data(collection_suffix)
        indexed_keys = set(indexed_data.keys())
        if not indexed_keys:
            self._log_data("Vectorstore is empty, indexing all incoming documents", tool_name="index_documents")
            yield from documents
            return

        docs_to_remove = set()

        for document in documents:
            key = self.key_fn(document)
            if key in indexed_keys and collection_suffix == indexed_data[key]['metadata'].get('collection'):
                if self.compare_fn(document, indexed_data[key]):
                    continue
                yield document
                docs_to_remove.update(self.remove_ids_fn(indexed_data, key))
            else:
                yield document

        if docs_to_remove:
            self._log_data(
                f"Removing {len(docs_to_remove)} documents from vectorstore that are already indexed with different updated_on.",
                tool_name="index_documents"
            )
            self.vectorstore.delete(ids=list(docs_to_remove))
    
    def _get_indexed_data(self, collection_suffix: str):
        raise NotImplementedError("Subclasses must implement this method")

    def key_fn(self, document: Document):
        raise NotImplementedError("Subclasses must implement this method")

    def compare_fn(self, document: Document, idx):
        raise NotImplementedError("Subclasses must implement this method")
    
    def remove_ids_fn(self, idx_data, key: str):
        raise NotImplementedError("Subclasses must implement this method")

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
        for doc in documents:
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
                        if chunker:=self._get_dependencies_chunker(processed_doc):
                            yield from chunker(file_content_generator=iter([processed_doc]), config=self._get_dependencies_chunker_config())
                        else:
                            yield processed_doc

    def remove_index(self, collection_suffix: str = ""):
        """Cleans the indexed data in the collection."""
        super()._clean_collection(collection_suffix=collection_suffix)
        return (f"Collection '{collection_suffix}' has been removed from the vector store.\n"
                f"Available collections: {self.list_collections()}")

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
        # build filter on top of collection_suffix
        filter = filter if isinstance(filter, dict) else json.loads(filter)
        if collection_suffix:
            filter.update({"collection": {
                "$eq": collection_suffix.strip()
            }})

        found_docs = super().search_documents(
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
                     collection_suffix: str = "",
                     filter: dict | str = {}, cut_off: float = 0.5,
                     search_top: int = 10, reranker: dict = {},
                     full_text_search: Optional[Dict[str, Any]] = None,
                     reranking_config: Optional[Dict[str, Dict[str, Any]]] = None,
                     extended_search: Optional[List[str]] = None,
                     **kwargs):
        """ Searches indexed documents in the vector store."""
        found_docs = super().stepback_search(
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
        return f"Found {len(found_docs)} documents matching the query\n{json.dumps(found_docs, indent=4)}" if found_docs else "No documents found matching the query."

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
        return super().stepback_summary(
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

    def get_available_tools(self):
        """
        Returns the standardized vector search tools (search operations only).
        Index operations are toolkit-specific and should be added manually to each toolkit.
        
        Returns:
            List of tool dictionaries with name, ref, description, and args_schema
        """
        return [
            {
                "name": "index_data",
                "mode": "index_data",
                "ref": self.index_data,
                "description": "Loads data to index.",
                "args_schema": create_model(
                    "IndexData",
                    __base__=BaseIndexDataParams,
                    **self._index_tool_params() if self._index_tool_params() else {}
                )
            },
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