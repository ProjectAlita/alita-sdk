import json
from json import dumps
from typing import Any, Optional, List, Dict
from pydantic import BaseModel, model_validator, Field
from langchain_core.tools import ToolException
from ..langchain.tools.vector import VectorAdapter
from langchain_core.messages import HumanMessage
from alita_tools.elitea_base import BaseToolApiWrapper
from logging import getLogger

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
    vectoradapter: Any = None
    pg_helper: Any = None
    
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
        values['embeddings'] = get_embeddings(values['embedding_model'], values['embedding_model_params'])
        values['vectorstore'] = get_vectorstore(values['vectorstore_type'], values['vectorstore_params'], embedding_func=values['embeddings'])
        values['vectoradapter'] = VectorAdapter(
            vectorstore=values['vectorstore'],
            embeddings=values['embeddings'],
            quota_params=None,
        )
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

    def index_documents(self, documents):
        from ..langchain.interfaces.llm_processor import add_documents
        logger.debug(f"Indexing documents: {documents}")
        logger.debug(self.vectoradapter)
        self.vectoradapter.delete_dataset(self.dataset)
        self.vectoradapter.persist()
        logger.debug(f"Deleted Dataset")
        #
        self.vectoradapter.vacuum()
        #
        documents_count = 0
        _documents = []
        for document in documents:
            documents_count += 1
            # logger.debug(f"Indexing document: {document}")
            try:
                _documents.append(document)
                if len(_documents) >= self.max_docs_per_add:
                    add_documents(vectorstore=self.vectoradapter.vectorstore, documents=_documents)
                    self.vectoradapter.persist()
                    _documents = []
            except Exception as e:
                from traceback import format_exc
                logger.error(f"Error: {format_exc()}")
                return {"status": "error", "message": f"Error: {format_exc()}"}
        if _documents:
            add_documents(vectorstore=self.vectoradapter.vectorstore, documents=_documents)
            self.vectoradapter.persist()
        return {"status": "ok", "message": f"successfully indexed {documents_count} documents"}

    def search_documents(self, query:str, doctype: str = 'code', 
                         filter:dict|str={}, cut_off: float=0.5,
                         search_top:int=10, reranker:dict = {}, 
                         full_text_search: Optional[Dict[str, Any]] = None,
                         reranking_config: Optional[Dict[str, Dict[str, Any]]] = None,
                         extended_search: Optional[List[str]] = None):
        """Enhanced search documents method using JSON configurations for full-text search and reranking"""
        from alita_tools.code.loaders.codesearcher import search_format as code_format
        
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
                document_items = self.vectoradapter.vectorstore.similarity_search_with_score(
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
                    chunk_items = self.vectoradapter.vectorstore.similarity_search_with_score(
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
                                fetch_items = self.vectoradapter.vectorstore.similarity_search_with_score(
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
            vector_items = self.vectoradapter.vectorstore.similarity_search_with_score(
                query, filter=filter, k=max_search_results
            )
            
        # Initialize document map for tracking by ID
        doc_map = {doc.metadata.get('id', f"idx_{i}"): (doc, score) 
                  for i, (doc, score) in enumerate(vector_items)}
        
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
        combined_items.sort(key=lambda x: x[1], reverse=True)
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
            return dumps(response, indent=2)

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
        return dumps(search_results, indent=2)

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