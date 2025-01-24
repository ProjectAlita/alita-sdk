# AlitaRetriever.py

**Path:** `src/alita_sdk/langchain/retrievers/AlitaRetriever.py`

## Data Flow

The data flow within the `AlitaRetriever.py` file is centered around the retrieval and processing of documents from a vector store. The primary data elements include the input query, documents retrieved from the vector store, and the final ranked and merged documents. The journey of data begins with the input query, which is optionally cleansed using the `cleanse_data` function. This cleansed input is then used to perform a similarity search in the vector store, retrieving a list of documents along with their scores. These documents are then reranked based on predefined weights and merged to form the final list of relevant documents. The data flow involves several intermediate steps, including the transformation of document metadata and the sorting of documents based on their scores.

Example:
```python
# Perform similarity search in the vector store
similarity_search = self.vectorstore.similarity_search_with_score(
    input,
    filter={'library': self.doc_library},
    k=self.fetch_k,
)
# Rerank the retrieved documents
reranked_docs = self._rerank_documents(similarity_search)
# Merge the reranked documents
final_docs = self.merge_results(input, reranked_docs)
```

## Functions Descriptions

### _rerank_documents

This function reranks the retrieved documents based on their scores and predefined weights. It takes a list of tuples (document, score) as input and returns a sorted list of documents with updated scores.

### merge_results

This function merges the results of the similarity search by grouping documents based on their source and selecting the top pages from each group. It takes the input query and a list of documents as input and returns a list of merged documents.

### get_relevant_documents

This function is the main entry point for retrieving relevant documents. It takes the input query and a callback manager as input, performs a similarity search, reranks the documents, and merges the results to return the final list of relevant documents.

## Dependencies Used and Their Descriptions

### langchain_core.retrievers.BaseRetriever

The `BaseRetriever` class from the `langchain_core.retrievers` module is the base class for the `AlitaRetriever` class. It provides the core functionality for document retrieval.

### langchain_core.documents.Document

The `Document` class from the `langchain_core.documents` module is used to represent the documents retrieved from the vector store.

### langchain_core.callbacks.CallbackManagerForRetrieverRun

The `CallbackManagerForRetrieverRun` class from the `langchain_core.callbacks` module is used to manage callbacks during the retrieval process.

### ..tools.log.print_log

The `print_log` function from the `..tools.log` module is used for logging debug information during the retrieval process.

### ..document_loaders.utils.cleanse_data

The `cleanse_data` function from the `..document_loaders.utils` module is used to cleanse the input query before performing the similarity search.

## Functional Flow

The functional flow of the `AlitaRetriever.py` file involves the following steps:
1. The input query is optionally cleansed using the `cleanse_data` function.
2. A similarity search is performed in the vector store using the cleansed input query.
3. The retrieved documents are reranked based on their scores and predefined weights.
4. The reranked documents are merged by grouping them based on their source and selecting the top pages from each group.
5. The final list of relevant documents is returned.

Example:
```python
# Cleanse the input query
if not self.no_cleanse:
    input = cleanse_data(input)
# Perform similarity search
similarity_search = self.vectorstore.similarity_search_with_score(
    input,
    filter={'library': self.doc_library},
    k=self.fetch_k,
)
# Rerank the retrieved documents
reranked_docs = self._rerank_documents(similarity_search)
# Merge the reranked documents
final_docs = self.merge_results(input, reranked_docs)
# Return the final list of relevant documents
return final_docs
```

## Endpoints Used/Created

The `AlitaRetriever.py` file does not explicitly define or call any endpoints. The primary interaction is with the vector store for performing similarity searches and retrieving documents.