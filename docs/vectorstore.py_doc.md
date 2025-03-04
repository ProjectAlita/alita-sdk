# vectorstore.py

**Path:** `src/alita_sdk/tools/vectorstore.py`

## Data Flow

The data flow within `vectorstore.py` revolves around the handling and processing of documents for indexing and searching within a vector store. The primary data elements include documents, search queries, and various configurations for indexing and searching. The data flow can be summarized as follows:

1. **Document Input:** Documents are provided as input to be indexed. These documents are typically in a generator format, as indicated by the `IndexDocumentsModel` class.
2. **Indexing:** The `index_documents` method processes the documents, adding them to the vector store in batches. Intermediate variables such as `_documents` are used to temporarily store documents before they are added to the vector store.
3. **Search Queries:** Search queries are received as input, along with optional filters and configurations. These queries are processed by the `search_documents` method, which interacts with the vector store to retrieve relevant documents based on similarity scores.
4. **Search Results:** The search results are processed and formatted based on the document type (e.g., code). The results are then returned as a JSON response.

Example:
```python
class IndexDocumentsModel(BaseModel):
    documents: Any = Field(description="Generator of documents to index")

class SearchDocumentsModel(BaseModel):
    query: str = Field(description="Search query")
    doctype: str = Field(description="Document type")
    filter: Optional[dict] = Field(
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
```

## Functions Descriptions

### `index_documents`

The `index_documents` function is responsible for indexing documents into the vector store. It takes a generator of documents as input and processes them in batches. The function deletes the existing dataset, vacuums the vector store, and then adds the documents in batches. If an error occurs during the indexing process, it logs the error and returns an error message.

**Inputs:**
- `documents`: A generator of documents to be indexed.

**Processing Logic:**
- Deletes the existing dataset.
- Vacuums the vector store.
- Adds documents in batches to the vector store.
- Logs errors if they occur.

**Outputs:**
- Returns a status message indicating the success or failure of the indexing process.

Example:
```python
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
```

### `search_documents`

The `search_documents` function handles the search queries and retrieves relevant documents from the vector store. It supports various configurations such as filters, full-text search, and reranking. The function processes the search query, applies filters, performs similarity search, and formats the results based on the document type.

**Inputs:**
- `query`: The search query string.
- `doctype`: The document type (e.g., code).
- `filter`: Optional filter for metadata of documents.
- `cut_off`: Optional cut-off value for search results.
- `search_top`: Optional number of search results to return.
- `full_text_search`: Optional full-text search configuration.
- `reranking_config`: Optional reranking configuration.
- `extended_search`: Optional list of chunk types to search for.

**Processing Logic:**
- Applies filters and performs similarity search.
- Processes full-text search if configured.
- Applies reranking rules if provided.
- Formats the search results based on the document type.

**Outputs:**
- Returns the search results as a JSON response.

Example:
```python
def search_documents(self, query:str, doctype: str = 'code', 
                     filter:dict={}, cut_off: float=0.5, 
                     search_top:int=10, reranker:dict = {}, 
                     full_text_search: Optional[Dict[str, Any]] = None,
                     reranking_config: Optional[Dict[str, Dict[str, Any]]] = None,
                     extended_search: Optional[List[str]] = None):
    """Enhanced search documents method using JSON configurations for full-text search and reranking"""
    from alita_tools.code.loaders.codesearcher import search_format as code_format
    
    if not filter:
        filter = None
        
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
```

## Dependencies Used and Their Descriptions

### `pydantic`

The `pydantic` library is used for data validation and settings management using Python type annotations. It provides the `BaseModel` class, which is used to define the data models for indexing and searching documents.

Example:
```python
from pydantic import BaseModel, Field
```

### `langchain_core.tools`

The `langchain_core.tools` module is used for handling tool exceptions. The `ToolException` class is imported to handle exceptions related to tool operations.

Example:
```python
from langchain_core.tools import ToolException
```

### `langchain_core.messages`

The `langchain_core.messages` module is used for handling messages. The `HumanMessage` class is imported to create human-readable messages for the LLM (Language Learning Model) interactions.

Example:
```python
from langchain_core.messages import HumanMessage
```

### `logging`

The `logging` module is used for logging debug and error messages throughout the code. The `getLogger` function is used to create a logger instance.

Example:
```python
from logging import getLogger

logger = getLogger(__name__)
```

## Functional Flow

The functional flow of `vectorstore.py` involves the following steps:

1. **Initialization:** The `VectorStoreWrapper` class is initialized with various parameters such as LLM, embedding model, vector store type, and their respective configurations.
2. **Validation:** The `validate_toolkit` method validates the provided configurations and initializes the vector store and embeddings.
3. **Indexing Documents:** The `index_documents` method is called to index documents into the vector store. It processes the documents in batches and handles errors if they occur.
4. **Searching Documents:** The `search_documents` method is called to search for documents based on the provided query and configurations. It applies filters, performs similarity search, processes full-text search, applies reranking, and formats the results.
5. **Stepback Search:** The `stepback_search` method is called to perform a stepback search, which involves converting the query into a more generic question, performing the search, and returning the results.
6. **Stepback Summary:** The `stepback_summary` method is called to get a summary of the search results using the stepback technique. It performs the stepback search and generates a summary based on the search results.
7. **Available Tools:** The `get_available_tools` method returns a list of available tools for indexing, searching, stepback search, and stepback summary.
8. **Run Tool:** The `run` method is called to execute a specific tool based on its name and provided arguments.

Example:
```python
class VectorStoreWrapper(BaseModel):
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
       