import json
import math
import types
from typing import Any, Optional, List, Dict, Callable, Generator, OrderedDict

from langchain_core.documents import Document
from pydantic import BaseModel, model_validator, Field
from ..langchain.tools.vector import VectorAdapter
from langchain_core.messages import HumanMessage
from alita_sdk.tools.elitea_base import BaseToolApiWrapper
from alita_sdk.tools.vector_adapters.VectorStoreAdapter import VectorStoreAdapterFactory
from logging import getLogger

from ..utils.logging import dispatch_custom_event
from ..utils.utils import IndexerKeywords

logger = getLogger(__name__)

class IndexDocumentsModel(BaseModel):
    documents: Any = Field(description="Generator of documents to index")

class SearchDocumentsModel(BaseModel):
    query: str = Field(description="Search query")
    doctype: str = Field(description="Document type")
    filter: Optional[dict | str] = Field(
        description='Filter for metadata of documents. Use JSON format for complex filters.',
        default=None)
    search_top: Optional[int] = Field(description="Number of search results", default=10)
    cut_off: Optional[float] = Field(description="Cut off value for search results", default=0.5)
    full_text_search: Optional[Dict[str, Any]] = Field(
        description="""Full text search configuration. Example:
        {
            "enabled": true,
            "weight": 0.3,
            "fields": ["content", "title"],
            "language": "english"
        }""",
        default=None
    )
    reranking_config: Optional[Dict[str, Dict[str, Any]]] = Field(
        description="""Reranking configuration. Example:
        {
            "field_name": {
                "weight": 1.0,
                "rules": {
                    "contains": "keyword",
                    "priority": "value",
                    "sort": "desc"
                }
            }
        }""",
        default=None
    )
    extended_search: Optional[List[str]] = Field(
        description="List of chunk types to search for (title, summary, propositions, keywords, documents)",
        default=None
    )

class StepBackSearchDocumentsModel(BaseModel):
    query: str = Field(description="Search query")
    doctype: str = Field(description="Document type")
    messages: Optional[list] = Field(description="Conversation history", default=[])
    filter: Optional[dict] = Field(description='Filter for metadata of documents. Use JSON format for complex filters.', default=None)
    search_top: Optional[int] = Field(description="Number of search results", default=10)
    cut_off: Optional[float] = Field(description="Cut off value for search results", default=0.5)
    full_text_search: Optional[Dict[str, Any]] = Field(
        description="""Full text search configuration. Example:
        {
            "enabled": true,
            "weight": 0.3,
            "fields": ["content", "title"],
            "language": "english"
        }""",
        default=None
    )
    extended_search: Optional[List[str]] = Field(
        description="List of chunk types to search for (title, summary, propositions, keywords, documents)",
        default=None
    )
    reranking_config: Optional[Dict[str, Dict[str, Any]]] = Field(
        description="""Reranking configuration. Example:
        {
            "field_name": {
                "weight": 1.0,
                "rules": {
                    "contains": "keyword",
                    "priority": "value",
                    "sort": "desc"
                }
            }
        }""",
        default=None
    )

STEPBACK_PROMPT = """Your task is to convert provided question into a more generic question that will be used for similarity search.
Remove all not important words, question words, but save all names, dates and acronym as in original question.

<input>
{input} 
</input>

Output:
"""

GET_ANSWER_PROMPT = """<search_results>
{search_results}
</search_results>

<conversation_history>
{messages}
</conversation_history>

Please answer the question based on provided search results.
Provided information is already processed and available in the context as list of possibly relevant pieces of the documents.
Use only provided information. Do not make up answer.
If you have no answer and you can not derive it from the context, please provide "I have no answer".
<question>
{input}
</question>
## Answer
Add <ANSWER> here

## Score
Score the answer from 0 to 100, where 0 is not relevant and 100 is very relevant.

## Citations
- source (score)
- source (score)
Make sure to provide unique source for each citation.

## Explanation
How did you come up with the answer?
"""

class VectorStoreWrapper(BaseToolApiWrapper):
    llm: Any
    embedding_model: str
    embedding_model_params: dict
    vectorstore_type: str
    vectorstore_params: dict
    max_docs_per_add: int = 100
    dataset: str = None
    embedding: Any = None
    vectorstore: Any = None
    # Review usage of old adapter
    vectoradapter: Any = None
    pg_helper: Any = None
    embeddings: Any = None
    process_document_func: Optional[Callable] = None
    # New adapter for vector database operations
    vector_adapter: Any = None

    @model_validator(mode='before')
    @classmethod
    def validate_toolkit(cls, values):
        from ..langchain.interfaces.llm_processor import get_embeddings, get_vectorstore
        logger.debug(f"Validating toolkit: {values}")
        if not values.get('vectorstore_type'):
            raise ValueError("Vectorstore type is required.")
        if not values.get('embedding_model'):
            raise ValueError("Embedding model is required.")
        if not values.get('vectorstore_params'):
            raise ValueError("Vectorstore parameters are required.")
        if not values.get('embedding_model_params'):
            raise ValueError("Embedding model parameters are required.")
        values["dataset"] = values.get('vectorstore_params').get('collection_name')
        if not values["dataset"]:
            raise ValueError("Collection name is required.")
        if not values.get('embeddings'):
            values['embeddings'] = get_embeddings(values['embedding_model'], values['embedding_model_params'])
        values['vectorstore'] = get_vectorstore(values['vectorstore_type'], values['vectorstore_params'], embedding_func=values['embeddings'])
        values['vectoradapter'] = VectorAdapter(
            vectorstore=values['vectorstore'],
            embeddings=values['embeddings'],
            quota_params=None,
        )
        # Initialize the new vector adapter
        values['vector_adapter'] = VectorStoreAdapterFactory.create_adapter(values['vectorstore_type'])
        logger.debug(f"Vectorstore wrapper initialized: {values}")
        return values

    def _init_pg_helper(self, language='english'):
        """Initialize PGVector helper if needed and not already initialized"""
        if self.pg_helper is None and hasattr(self.vectorstore, 'connection_string') and hasattr(self.vectorstore, 'collection_name'):
            try:
                from .pgvector_search import PGVectorSearch
                self.pg_helper = PGVectorSearch(
                    self.vectorstore.connection_string,
                    self.vectorstore.collection_name,
                    language=language
                )
            except ImportError:
                logger.warning("PGVectorSearch not available - full-text search will be limited")
            except Exception as e:
                logger.error(f"Failed to initialize PGVectorSearch: {str(e)}")

    def _remove_collection(self):
        """
        Remove the vectorstore collection entirely.
        """
        self._log_data(
            f"Remove collection '{self.dataset}'",
            tool_name="_remove_collection"
        )
        self.vector_adapter.remove_collection(self, self.dataset)
        self._log_data(
            f"Collection '{self.dataset}' has been removed. ",
            tool_name="_remove_collection"
        )

    def _get_indexed_ids(self, collection_suffix: Optional[str] = '') -> List[str]:
        """Get all indexed document IDs from vectorstore"""
        return self.vector_adapter.get_indexed_ids(self, collection_suffix)

    def list_collections(self) -> Any:
        """List all collections in the vectorstore.
        Returns a list of collection names, or if no collections exist,
        returns a dict with an empty list and a message."""
        raw = self.vector_adapter.list_collections(self)
        # Normalize raw result to a list of names
        if not raw:
            # No collections found
            return {"collections": [], "message": "No indexed collections"}
        if isinstance(raw, str):
            # e.g., Chroma adapter returns comma-separated string
            cols = [c for c in raw.split(',') if c]
        else:
            try:
                cols = list(raw)
            except Exception:
                # Unexpected type, return raw directly
                return raw
        if not cols:
            return {"collections": [], "message": "No indexed collections"}
        return cols

    def _clean_collection(self, collection_suffix: str = ''):
        """
        Clean the vectorstore collection by deleting all indexed data.
        """
        self._log_data(
            f"Cleaning collection '{self.dataset}'",
            tool_name="_clean_collection"
        )
        self.vector_adapter.clean_collection(self, collection_suffix)
        self._log_data(
            f"Collection '{self.dataset}' has been cleaned. ",
            tool_name="_clean_collection"
        )

    def _get_indexed_data(self, collection_name: str):
        """ Get all indexed data from vectorstore for non-code content """
        return self.vector_adapter.get_indexed_data(self, collection_name)

    def _get_code_indexed_data(self, collection_suffix: str) -> Dict[str, Dict[str, Any]]:
        """ Get all indexed data from vectorstore for code content """
        return self.vector_adapter.get_code_indexed_data(self, collection_suffix)

    def _add_to_collection(self, entry_id, new_collection_value):
        """Add a new collection name to the `collection` key in the `metadata` column."""
        self.vector_adapter.add_to_collection(self, entry_id, new_collection_value)

    def _reduce_duplicates(
            self,
            documents: Generator[Any, None, None],
            collection_suffix: str,
            get_indexed_data: Callable,
            key_fn: Callable,
            compare_fn: Callable,
            remove_ids_fn: Callable,
            log_msg: str = "Verification of documents to index started"
    ) -> List[Any]:
        """Generic duplicate reduction logic for documents."""
        self._log_data(log_msg, tool_name="index_documents")
        indexed_data = get_indexed_data(collection_suffix)
        indexed_keys = set(indexed_data.keys())
        if not indexed_keys:
            self._log_data("Vectorstore is empty, indexing all incoming documents", tool_name="index_documents")
            return list(documents)

        final_docs = []
        docs_to_remove = set()

        for document in documents:
            key = key_fn(document)
            key = key if isinstance(key, str) else str(key)
            if key in indexed_keys and collection_suffix == indexed_data[key]['metadata'].get('collection'):
                if compare_fn(document, indexed_data[key]):
                    # Disabled addition of new collection to already indexed documents
                    # # check metadata.collection and update if needed
                    # for update_collection_id in remove_ids_fn(indexed_data, key):
                    #     self._add_to_collection(
                    #         update_collection_id,
                    #         collection_suffix
                    #     )
                    continue
                final_docs.append(document)
                docs_to_remove.update(remove_ids_fn(indexed_data, key))
            else:
                final_docs.append(document)

        if docs_to_remove:
            self._log_data(
                f"Removing {len(docs_to_remove)} documents from vectorstore that are already indexed with different updated_on.",
                tool_name="index_documents"
            )
            self.vectorstore.delete(ids=list(docs_to_remove))

        return final_docs

    def _reduce_non_code_duplicates(self, documents: Generator[Any, None, None], collection_suffix: str) -> List[Any]:
        return self._reduce_duplicates(
            documents,
            collection_suffix,
            self._get_indexed_data,
            lambda doc: doc.metadata.get('id'),
            lambda doc, idx: (
                    doc.metadata.get('updated_on') and
                    idx['metadata'].get('updated_on') and
                    doc.metadata.get('updated_on') == idx['metadata'].get('updated_on')
            ),
            lambda idx_data, key: (
                    idx_data[key]['all_chunks'] +
                    [idx_data[dep_id]['id'] for dep_id in idx_data[key][IndexerKeywords.DEPENDENT_DOCS.value]] +
                    [chunk_db_id for dep_id in idx_data[key][IndexerKeywords.DEPENDENT_DOCS.value]
                     for chunk_db_id in idx_data[dep_id]['all_chunks']]
            ),
            log_msg="Verification of documents to index started"
        )

    def _reduce_code_duplicates(self, documents: Generator[Any, None, None], collection_suffix: str) -> List[Any]:
        return self._reduce_duplicates(
            documents,
            collection_suffix,
            self._get_code_indexed_data,
            lambda doc: doc.metadata.get('filename'),
            lambda doc, idx: (
                    doc.metadata.get('commit_hash') and
                    idx.get('commit_hashes') and
                    doc.metadata.get('commit_hash') in idx.get('commit_hashes')
            ),
            lambda idx_data, key: idx_data[key]['ids'],
            log_msg="Verification of code documents to index started"
        )

    def index_documents(self, documents: Generator[Document, None, None], collection_suffix: str, progress_step: int = 20, clean_index: bool = True, is_code: bool = False):
        """ Index documents in the vectorstore.

        Args:
            documents (Any): Generator or list of documents to index.
            progress_step (int): Step for progress reporting, default is 20.
            clean_index (bool): If True, clean the index before re-indexing all documents.
        """

        from ..langchain.interfaces.llm_processor import add_documents

        self._log_tool_event(message=f"Starting the indexing... Parameters: {collection_suffix=}, {clean_index=}, {is_code}", tool_name="index_documents")
        # pre-process documents if needed (find duplicates, etc.)
        if clean_index:
            logger.info("Cleaning index before re-indexing all documents.")
            self._log_data("Cleaning index before re-indexing all documents. Previous index will be removed", tool_name="index_documents")
            try:
                self._clean_collection(collection_suffix)
                self.vectoradapter.persist()
                self.vectoradapter.vacuum()
                self._log_data("Previous index has been removed",
                               tool_name="index_documents")
            except Exception as e:
                logger.warning(f"Failed to clean index: {str(e)}. Continuing with re-indexing.")
            if isinstance(documents, types.GeneratorType):
                documents = list(documents)
        else:
            self._log_tool_event(
                message="Filter for duplicates",
                tool_name="index_documents")
            # remove duplicates based on metadata 'id' and 'updated_on' or 'commit_hash' fields
            documents = self._reduce_code_duplicates(documents, collection_suffix) if is_code \
                else self._reduce_non_code_duplicates(documents, collection_suffix)
            self._log_tool_event(
                message="All the duplicates were filtered out. Proceeding with indexing.",
                tool_name="index_documents")

        if not documents or len(documents) == 0:
            logger.info("No new documents to index after duplicate check.")
            return {"status": "ok", "message": "No new documents to index."}

        # if func is provided, apply it to documents
        # used for processing of documents before indexing,
        # e.g. to avoid time-consuming operations for documents that are already indexed
        self._log_tool_event(message=f"Processing the dependent documents (attachments, etc.)", tool_name="index_documents")
        dependent_docs_generator = self.process_document_func(documents) if self.process_document_func else []
        # notify user about missed required metadata fields: id, updated_on
        # it is not required to have them, but it is recommended to have them for proper re-indexing and duplicate detection
        for doc in documents:
            if 'id' not in doc.metadata or 'updated_on' not in doc.metadata:
                logger.warning(f"Document is missing required metadata field 'id' or 'updated_on': {doc.metadata}")

        logger.debug(f"Indexing documents: {documents}")
        logger.debug(self.vectoradapter)

        documents = documents + list(dependent_docs_generator)

        self._log_tool_event(message=f"Documents for indexing were processed. Total documents: {len(documents)}",
                             tool_name="index_documents")

        # if collection_suffix is provided, add it to metadata of each document
        if collection_suffix:
            for doc in documents:
                if not doc.metadata.get('collection'):
                    doc.metadata['collection'] = collection_suffix
                else:
                    doc.metadata['collection'] += f";{collection_suffix}"

        total_docs = len(documents)
        documents_count = 0
        _documents = []
        self._log_tool_event(message=f"Starting the indexing of processed documents. Total documents: {len(documents)}",
                             tool_name="index_documents")
        # set default progress step to 20 if out of 0...100 or None
        progress_step = 20 if progress_step not in range(0, 100) else progress_step
        next_progress_point = progress_step
        for document in documents:
            documents_count += 1
            # logger.debug(f"Indexing document: {document}")
            try:
                _documents.append(document)
                if len(_documents) >= self.max_docs_per_add:
                    add_documents(vectorstore=self.vectorstore, documents=_documents)
                    _documents = []

                percent = math.floor((documents_count / total_docs) * 100)
                if percent >= next_progress_point:
                    msg = f"Indexing progress: {percent}%. Processed {documents_count} of {total_docs} documents."
                    logger.debug(msg)
                    self._log_data(msg)
                    next_progress_point += progress_step
            except Exception:
                from traceback import format_exc
                logger.error(f"Error: {format_exc()}")
                return {"status": "error", "message": f"Error: {format_exc()}"}
        if _documents:
            add_documents(vectorstore=self.vectorstore, documents=_documents)
        return {"status": "ok", "message": f"successfully indexed {documents_count} documents"}

    def search_documents(self, query:str, doctype: str = 'code', 
                         filter:dict|str={}, cut_off: float=0.5,
                         search_top:int=10, full_text_search: Optional[Dict[str, Any]] = None,
                         extended_search: Optional[List[str]] = None,
                         reranker: dict = {}, reranking_config: Optional[Dict[str, Dict[str, Any]]] = None
                         ):
        """Enhanced search documents method using JSON configurations for full-text search and reranking"""
        from alita_sdk.tools.code.loaders.codesearcher import search_format as code_format
        
        if not filter:
            filter = None
        else:
            if isinstance(filter, str):
                filter = json.loads(filter)

        # Extended search implementation
        if extended_search:
            # Track unique documents by source and chunk_id
            unique_docs = {}
            chunk_type_scores = {}  # Store scores by document identifier
            # Create initial set of results from documents
            if filter is None:
                document_filter = {"chunk_type": {"$eq": "document"}}
            else:
                document_filter = {
                    "$and": [
                        filter,
                        {"chunk_type": {"$eq": "document"}}
                    ]
                }
                
            try:
                document_items = self.vectorstore.similarity_search_with_score(
                    query, filter=document_filter, k=search_top
                )                
                # Add document results to unique docs
                vector_items = document_items
                for doc, score in document_items:
                    source = doc.metadata.get('source')
                    chunk_id = doc.metadata.get('chunk_id')
                    doc_id = f"{source}_{chunk_id}" if source and chunk_id else str(doc.metadata.get('id', id(doc)))
                    
                    if doc_id not in unique_docs or score > chunk_type_scores.get(doc_id, 0):
                        unique_docs[doc_id] = doc
                        chunk_type_scores[doc_id] = score
            except Exception as e:
                logger.warning(f"Error searching for document chunks: {str(e)}")
            
            # First search for specified chunk types (title, summary, propositions, keywords)
            valid_chunk_types = ["title", "summary", "propositions", "keywords"]
            chunk_types_to_search = [ct for ct in extended_search if ct in valid_chunk_types]
            
            # Search for each chunk type separately
            for chunk_type in chunk_types_to_search:
                if filter is None:
                    chunk_filter = {"chunk_type": {"$eq": chunk_type}}
                else:
                    chunk_filter = {
                        "$and": [
                            filter,
                            {"chunk_type": {"$eq": chunk_type}}
                        ]
                    }
                
                try:
                    chunk_items = self.vectorstore.similarity_search_with_score(
                        query, filter=chunk_filter, k=search_top
                    )
                    
                    logger.debug(f"Chunk items for {chunk_type}: {chunk_items[0]}")
                    
                    for doc, score in chunk_items:
                        # Create unique identifier for document
                        source = doc.metadata.get('source')
                        chunk_id = doc.metadata.get('chunk_id')
                        doc_id = f"{source}_{chunk_id}" if source and chunk_id else str(doc.metadata.get('id', id(doc)))
                        
                        # Store document and its score
                        if doc_id not in unique_docs:
                            unique_docs[doc_id] = doc
                            chunk_type_scores[doc_id] = score
                            # Create a filter with proper operators 
                            doc_filter_parts = [
                                {"source": {"$eq": source}},
                                {"chunk_id": {"$eq": chunk_id}},
                                {"chunk_type": {"$eq": "document"}}
                            ]
                            
                            if filter is not None:
                                doc_filter = {
                                    "$and": [filter] + doc_filter_parts
                                }
                            else:
                                doc_filter = {
                                    "$and": doc_filter_parts
                                }
                                
                            try:
                                fetch_items = self.vectorstore.similarity_search_with_score(
                                    query, filter=doc_filter, k=1
                                )
                                if fetch_items:
                                    vector_items.append(fetch_items[0])

                            except Exception as e:
                                logger.warning(f"Error retrieving document chunk for {source}_{chunk_id}: {str(e)}")
                except Exception as e:
                    logger.warning(f"Error searching for chunk type {chunk_type}: {str(e)}")
            
        else:
            # Default search behavior (unchanged)
            max_search_results = 30 if search_top * 3 > 30 else search_top * 3
            vector_items = self.vectorstore.similarity_search_with_score(
                query, filter=filter, k=max_search_results
            )
            
        # Initialize document map for tracking by ID
        doc_map = {
            (
                f"{doc.metadata.get('id', f'idx_{i}')}_{doc.metadata['chunk_id']}"
                if 'chunk_id' in doc.metadata
                else doc.metadata.get('id', f"idx_{i}")
            ): (doc, 1 - score)
            for i, (doc, score) in enumerate(vector_items)
        }

        # Sort the items by the new score in descending order
        doc_map = OrderedDict(
            sorted(doc_map.items(), key=lambda x: x[1][1], reverse=True)
        )
        
        # Process full-text search if configured
        if full_text_search and full_text_search.get('enabled') and full_text_search.get('fields'):
            language = full_text_search.get('language', 'english')
            self._init_pg_helper(language)
            if self.pg_helper:
                vector_weight = 1.0  # Default vector weight
                text_weight = full_text_search.get('weight', 0.3)
                
                # Query each specified field
                for field_name in full_text_search.get('fields', []):
                    try:
                        text_results = self.pg_helper.full_text_search(field_name, query)
                        
                        # Combine text search results with vector results
                        for result in text_results:
                            doc_id = result['id']
                            text_score = result['text_score']
                            
                            if doc_id in doc_map:
                                # Document exists in vector results, combine scores
                                doc, vector_score = doc_map[doc_id]
                                combined_score = (vector_score * vector_weight) + (text_score * text_weight)
                                doc_map[doc_id] = (doc, combined_score)
                            else:
                                # Document is new from text search, fetch and add if possible
                                doc_data = self.pg_helper.get_documents_by_ids([doc_id]).get(doc_id)
                                if doc_data:
                                    from langchain_core.documents import Document
                                    doc = Document(
                                        page_content=doc_data.get('document', ''),
                                        metadata=doc_data.get('cmetadata', {})
                                    )
                                    # Use weighted text score for new documents
                                    doc_map[doc_id] = (doc, text_score * text_weight)
                    except Exception as e:
                        logger.error(f"Full-text search error on field {field_name}: {str(e)}")
            
        # Convert the document map back to a list
        combined_items = list(doc_map.values())
        
        # Apply reranking rules
        if reranking_config:
            combined_items = self._apply_reranking(combined_items, reranking_config)
        elif reranker:  # Fallback to legacy reranker parameter
            combined_items = self._apply_reranking(combined_items, reranker)
        
        # Apply cutoff filter
        if cut_off:
            # Filter out items above the cutoff score (since the lower the score, the better)
            combined_items = [item for item in combined_items if abs(item[1]) >= cut_off]
        
        # Sort by score and limit results
        # DISABLED: for chroma we want ascending order (lower score is better), for others descending
        # combined_items.sort(key=lambda x: x[1], reverse= self.vectorstore_type.lower() != 'chroma')
        combined_items = combined_items[:search_top]

        # Format output based on doctype
        if doctype == 'code':
            return code_format(combined_items)
        else:
            response = []
            for doc, score in combined_items:
                response.append({
                    'page_content': doc.page_content,
                    'metadata': doc.metadata,
                    'score': score
                })
            return response

    def _apply_reranking(self, items, reranker):
        """Apply reranking rules to search results"""
        if not items:
            return items
        
        # Create a copy of items with mutable scores for reranking
        reranked_items = [(doc, score) for doc, score in items]
        
        for field_name, config in reranker.items():
            weight = config.get("weight", 1.0)
            rules = config.get("rules", {})
            
            for i, (doc, score) in enumerate(reranked_items):
                metadata = doc.metadata
                field_value = metadata.get(field_name)
                
                if field_value is not None:
                    # Apply rules-based reranking
                    for rule_type, rule_value in rules.items():
                        if rule_type == "contains" and isinstance(rule_value, str) and isinstance(field_value, str):
                            if rule_value.lower() in field_value.lower():
                                # Boost score if field contains the rule value
                                reranked_items[i] = (doc, score * (1 + weight))
                        
                        elif rule_type == "priority":
                            # Apply priority rule based on exact match
                            if str(field_value).lower() == str(rule_value).lower():
                                reranked_items[i] = (doc, score * (1 + weight))
        
        # Handle sort rules after individual score adjustments
        for field_name, config in reranker.items():
            rules = config.get("rules", {})
            if "sort" in rules:
                sort_direction = rules["sort"]
                # Assuming sort can be "asc" or "desc"
                reverse_sort = sort_direction.lower() == "desc"
                
                # Sort based on the specified field
                reranked_items.sort(
                    key=lambda x: (x[0].metadata.get(field_name, None) is not None, 
                                  x[0].metadata.get(field_name, ""), 
                                  x[1]),
                    reverse=reverse_sort
                )
        
        # Re-sort by score if no sort rules were applied
        if not any("sort" in config.get("rules", {}) for config in reranker.values()):
            reranked_items.sort(key=lambda x: x[1], reverse=True)
        
        return reranked_items

    def stepback_search(self, query:str, messages: list, doctype: str = 'code', 
                        filter:dict={}, cut_off: float=0.5, search_top:int=10, 
                        full_text_search: Optional[Dict[str, Any]] = None,
                        reranking_config: Optional[Dict[str, Dict[str, Any]]] = None,
                        extended_search: Optional[List[str]] = None):
        """Enhanced stepback search using JSON configs for full-text search and reranking"""
        result = self.llm.invoke([
            HumanMessage(
                content=[
                    {
                        "type": "text", 
                        "text": STEPBACK_PROMPT.format(input=query, messages=messages)
                    }
                ]
            )
        ])
        search_results = self.search_documents(
            result.content, doctype, filter, cut_off, search_top, 
            full_text_search=full_text_search,
            reranking_config=reranking_config,
            extended_search=extended_search
        )
        return search_results

    def stepback_summary(self, query:str, messages: list, doctype: str = 'code', 
                         filter:dict={}, cut_off: float=0.5, search_top:int=10, 
                         full_text_search: Optional[Dict[str, Any]] = None,
                         reranking_config: Optional[Dict[str, Dict[str, Any]]] = None,
                         extended_search: Optional[List[str]] = None):
        """Enhanced stepback summary using JSON configs for full-text search and reranking"""
        search_results = self.stepback_search(
            query, messages, doctype, filter, cut_off, search_top, 
            full_text_search=full_text_search,
            reranking_config=reranking_config,
            extended_search=extended_search
        )
        result = self.llm.invoke([
            HumanMessage(
                content=[
                    {
                        "type": "text", 
                        "text": GET_ANSWER_PROMPT.format(input=query, search_results=search_results, messages=messages)
                    }
                ]
            )
        ])
        return result.content

    def _log_data(self, message: str, tool_name: str = "index_data"):
        """Log data and dispatch custom event for indexing progress"""

        try:
            dispatch_custom_event(
                name="thinking_step_update",
                data={
                    "message": message,
                    "tool_name": tool_name,
                    "toolkit": "vectorstore",
                },
            )
        except Exception as e:
            logger.warning(f"Failed to dispatch progress event: {str(e)}")

    def get_available_tools(self):
        return [
            {
                "ref": self.index_documents,
                "name": "indexDocuments",
                "description": "Index documents in the vectorstore",
                "args_schema": IndexDocumentsModel
            },
            {
                "ref": self.search_documents,
                "name": "searchDocuments",
                "description": "Search documents in the vectorstore",
                "args_schema": SearchDocumentsModel
            },
            {
                "ref": self.stepback_search,
                "name": "stepbackSearch",
                "description": "Search in the vectorstore using stepback technique",
                "args_schema": StepBackSearchDocumentsModel
            },
            {
                "ref": self.stepback_summary,
                "name": "stepbackSummary",
                "description": "Get summary of search results using stepback technique",
                "args_schema": StepBackSearchDocumentsModel
            }
        ]
