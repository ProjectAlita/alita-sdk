# vectorstore.py

**Path:** `src/alita_sdk/tools/vectorstore.py`

## Data Flow

The data flow within `vectorstore.py` revolves around the management and querying of vector stores for document indexing and retrieval. The primary data elements include documents to be indexed, search queries, and the resulting search outputs. The data originates from the input parameters provided to the functions, such as documents for indexing or search queries. These inputs are processed through various transformations, including validation, embedding generation, and vector store interactions. The data is temporarily stored in variables and class attributes, facilitating intermediate steps like filtering, reranking, and full-text search. The final output is either the indexed documents or the search results, which are returned to the caller.

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
```
* This snippet shows the initialization of the `VectorStoreWrapper` class, where various parameters and attributes are defined to manage the data flow within the class.

## Functions Descriptions

### `validate_toolkit`

This function validates the toolkit configuration by checking the presence of essential parameters like `vectorstore_type`, `embedding_model`, and their respective parameters. It initializes embeddings and the vector store using helper functions and sets up the `vectoradapter`.

### `index_documents`

This function indexes a batch of documents into the vector store. It deletes the existing dataset, processes the documents in batches, and adds them to the vector store. It handles errors and returns the status of the indexing operation.

### `search_documents`

This function performs a search on the vector store using the provided query and optional filters. It supports extended search configurations, full-text search, and reranking. The results are formatted based on the document type and returned as a JSON string.

### `stepback_search`

This function performs a stepback search by first generating a generic query using the LLM and then searching the vector store with the generated query. It returns the search results as a JSON string.

### `stepback_summary`

This function generates a summary of the search results using the stepback search technique. It invokes the LLM to generate the summary based on the search results and the original query.

### `get_available_tools`

This function returns a list of available tools with their references, names, descriptions, and argument schemas.

### `run`

This function executes a specified tool by its name, passing the provided arguments to the tool's reference function. It raises an exception if the tool name is unknown.

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
* This snippet shows the `index_documents` function, which processes and indexes documents in batches, handling errors and logging the process.

## Dependencies Used and Their Descriptions

### `pydantic`

Used for data validation and settings management through the `BaseModel` class and `Field` function.

### `langchain_core.tools`

Provides the `ToolException` class for handling tool-related exceptions.

### `langchain_core.messages`

Provides the `HumanMessage` class for handling human-readable messages.

### `logging`

Used for logging debug and error messages throughout the code.

### `..langchain.tools.vector`

Provides the `VectorAdapter` class for interacting with the vector store.

### `..langchain.interfaces.llm_processor`

Provides helper functions `get_embeddings` and `get_vectorstore` for initializing embeddings and vector stores, and `add_documents` for adding documents to the vector store.

Example:
```python
from pydantic import BaseModel, model_validator, Field
from langchain_core.tools import ToolException
from ..langchain.tools.vector import VectorAdapter
from langchain_core.messages import HumanMessage
from logging import getLogger
```
* This snippet shows the import statements for the dependencies used in the file.

## Functional Flow

1. **Initialization**: The `VectorStoreWrapper` class is initialized with various parameters and attributes required for managing the vector store and embeddings.
2. **Validation**: The `validate_toolkit` function validates the toolkit configuration and initializes embeddings and the vector store.
3. **Indexing**: The `index_documents` function processes and indexes documents in batches, handling errors and logging the process.
4. **Searching**: The `search_documents` function performs a search on the vector store using the provided query and optional filters, supporting extended search configurations, full-text search, and reranking.
5. **Stepback Search**: The `stepback_search` function generates a generic query using the LLM and searches the vector store with the generated query.
6. **Stepback Summary**: The `stepback_summary` function generates a summary of the search results using the stepback search technique.
7. **Tool Management**: The `get_available_tools` function returns a list of available tools, and the `run` function executes a specified tool by its name.

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
* This snippet shows the `search_documents` function, which performs a search on the vector store, processes the results, and applies reranking and cutoff filters.

## Endpoints Used/Created

The `vectorstore.py` file does not explicitly define or call any external endpoints. The primary interactions are with the vector store and the LLM for generating queries and summaries. The vector store interactions are handled through the `VectorAdapter` class, and the LLM interactions are managed through the `llm` attribute of the `VectorStoreWrapper` class.