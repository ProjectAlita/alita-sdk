import json
import math
from collections import OrderedDict
from logging import getLogger
from typing import Any, Optional, List, Dict, Generator

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage
from langchain_core.tools import ToolException
from psycopg.errors import DataException
from pydantic import BaseModel, model_validator, Field

from alita_sdk.tools.elitea_base import BaseToolApiWrapper
from alita_sdk.tools.vector_adapters.VectorStoreAdapter import VectorStoreAdapterFactory
from ..utils.logging import dispatch_custom_event

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

class VectorStoreWrapperBase(BaseToolApiWrapper):
    llm: Any
    embedding_model: Optional[str] = None
    vectorstore_type: Optional[str]  = None
    vectorstore_params: Optional[dict]  = None
    max_docs_per_add: int = 20
    dataset: Optional[str] = None
    vectorstore: Any = None
    pg_helper: Any = None
    embeddings: Any = None
    # New adapter for vector database operations
    vector_adapter: Any = None

    @model_validator(mode='before')
    @classmethod
    def validate_toolkit(cls, values):
        from ..langchain.interfaces.llm_processor import get_vectorstore
        logger.debug(f"Validating toolkit: {values}")
        values["dataset"] = values.get('collection_name')

        if values.get('alita') and values.get('embedding_model'):
            values['embeddings'] = values.get('alita').get_embeddings(values.get('embedding_model'))

        if values.get('vectorstore_type') and values.get('vectorstore_params') and values.get('embedding_model'):
            values['vectorstore'] = get_vectorstore(values['vectorstore_type'], values['vectorstore_params'], embedding_func=values['embeddings'])
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

    def _similarity_search_with_score(self, query: str, filter: dict = None, k: int = 10):
        """
        Perform similarity search with proper exception handling for DataException.

        Args:
            query: Search query string
            filter: Optional filter dictionary
            k: Number of results to return

        Returns:
            List of (Document, score) tuples

        Raises:
            ToolException: When DataException occurs or other search errors
        """
        try:
            return self.vectorstore.similarity_search_with_score(
                query, filter=filter, k=k
            )
        except DataException as dimException:
            exception_str = str(dimException)
            if 'different vector dimensions' in exception_str:
                logger.error(f"Data exception: {exception_str}")
                raise ToolException(f"Global search cannot be completed since collections were indexed using "
                                    f"different embedding models. Use search within a single collection."
                                    f"\nDetails: {exception_str}")
            raise ToolException(f"Data exception during search. Possibly invalid filter: {exception_str}")
        except Exception as e:
            logger.error(f"Error during similarity search: {str(e)}")
            raise ToolException(f"Search failed: {str(e)}")

    def list_collections(self) -> List[str]:
        """List all collections in the vectorstore."""

        collections = self.vector_adapter.list_collections(self)
        if not collections:
            return "No indexed collections"
        return collections

    def get_index_meta(self, index_name: str):
        index_metas = self.vector_adapter.get_index_meta(self, index_name)
        if len(index_metas) > 1:
            raise RuntimeError(f"Multiple index_meta documents found: {index_metas}")
        return index_metas[0] if index_metas else None

    def _clean_collection(self, index_name: str = ''):
        """
        Clean the vectorstore collection by deleting all indexed data.
        """
        self._log_tool_event(
            f"Cleaning collection '{self.dataset}'",
            tool_name="_clean_collection"
        )
        self.vector_adapter.clean_collection(self, index_name)
        self._log_tool_event(
            f"Collection '{self.dataset}' has been cleaned. ",
            tool_name="_clean_collection"
        )

    def index_documents(self, documents: Generator[Document, None, None], index_name: str, progress_step: int = 20, clean_index: bool = True):
        """ Index documents in the vectorstore.

        Args:
            documents (Any): Generator or list of documents to index.
            progress_step (int): Step for progress reporting, default is 20.
            clean_index (bool): If True, clean the index before re-indexing all documents.
        """
        if clean_index:
            self._clean_index(index_name)

        return self._save_index(list(documents), index_name, progress_step)

    def _clean_index(self, index_name: str):
        logger.info("Cleaning index before re-indexing all documents.")
        self._log_tool_event("Cleaning index before re-indexing all documents. Previous index will be removed", tool_name="index_documents")
        try:
            self._clean_collection(index_name)
            self._log_tool_event("Previous index has been removed",
                           tool_name="index_documents")
        except Exception as e:
            logger.warning(f"Failed to clean index: {str(e)}. Continuing with re-indexing.")

    def _save_index(self, documents: list[Document], index_name: Optional[str] = None, progress_step: int = 20):
        from ..langchain.interfaces.llm_processor import add_documents
        #
        for doc in documents:
            if 'id' not in doc.metadata or 'updated_on' not in doc.metadata:
                logger.warning(f"Document is missing required metadata field 'id' or 'updated_on': {doc.metadata}")

        logger.debug(f"Indexing documents: {documents}")

        # if index_name is provided, add it to metadata of each document
        if index_name:
            for doc in documents:
                if not doc.metadata.get('collection'):
                    doc.metadata['collection'] = index_name
                else:
                    doc.metadata['collection'] += f";{index_name}"

        total_docs = len(documents)
        documents_count = 0
        _documents = []

        # set default progress step to 20 if out of 0...100 or None
        progress_step = 20 if progress_step not in range(0, 100) else progress_step
        next_progress_point = progress_step
        for document in documents:
            if not document.page_content:
                # To avoid case when all documents have empty content
                # See llm_processor.add_documents which exclude metadata of docs with empty content
                continue
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
                    self._log_tool_event(msg)
                    next_progress_point += progress_step
            except Exception:
                from traceback import format_exc
                logger.error(f"Error: {format_exc()}")
                return {"status": "error", "message": f"Error: {format_exc()}"}
        if _documents:
            add_documents(vectorstore=self.vectorstore, documents=_documents)
        return {"status": "ok", "message": f"successfully indexed {documents_count} documents" if documents_count > 0
        else "no documents to index"}

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
                document_items = self._similarity_search_with_score(
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
                    chunk_items = self._similarity_search_with_score(
                        query, filter=chunk_filter, k=search_top
                    )

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
                                fetch_items = self._similarity_search_with_score(
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
            vector_items = self._similarity_search_with_score(
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
