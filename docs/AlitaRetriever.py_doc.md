# AlitaRetriever.py

**Path:** `src/alita_sdk/langchain/retrievers/AlitaRetriever.py`

## Data Flow

The data flow within the `AlitaRetriever.py` file is centered around the retrieval and processing of documents from a vector store. The primary data elements include the input query, documents retrieved from the vector store, and the final ranked and merged documents. The journey of data begins with the input query, which is optionally cleansed using the `cleanse_data` function. This cleansed input is then used to perform a similarity search in the vector store, retrieving a list of documents along with their scores. These documents are then reranked based on predefined weights and merged to form the final set of relevant documents. The data flow involves several transformations, including cleansing, similarity search, reranking, and merging. Intermediate variables such as `test_docs`, `docs`, and `_docs` are used to store temporary results during these transformations.

Example:
```python
# Cleansing the input data if required
if not self.no_cleanse:
    test_docs = self.vectorstore.similarity_search_with_score(
        input,
        filter={"$and": [{"library": self.doc_library}, {"type": "data"}]},
        k=1,
    )
    if test_docs and "data" in test_docs[0][0].metadata:
        input = cleanse_data(input)
```
In this example, the input query is cleansed if necessary, and the cleansed input is then used for further processing.

## Functions Descriptions

### _rerank_documents

This function reranks the retrieved documents based on their scores and predefined weights. It takes a list of tuples (documents and their scores) as input and returns a sorted list of documents with updated scores.

Example:
```python
def _rerank_documents(self, documents: List[tuple]):
    _documents = []
    for (document, score) in documents:
        item = {
            "page_content": document.page_content,
            "metadata": document.metadata,
            "score": score * self.weights.get(document.metadata['type'], 1.0),
        }
        if "data" in item["metadata"]:
            item["page_content"] = item["metadata"].pop("data")
        _documents.append(item)
    return sorted(
        _documents,
        key=lambda x: x["score"],
        reverse=not self.lower_score_better,
    )
```
This function iterates over the documents, updates their scores based on the weights, and sorts them accordingly.

### merge_results

This function merges the results from the similarity search to form the final set of relevant documents. It takes the input query and a list of documents as input and returns a list of merged documents.

Example:
```python
def merge_results(self, input: str, docs: List[dict]):
    results = {}
    for doc in docs:
        if doc['metadata']['source'] not in results.keys():
            results[doc['metadata']['source']] = {
                'page_content': [],
                'metadata': {
                    'source': doc['metadata']['source'],
                },
            }
            documents = self.vectorstore.similarity_search_with_score(
                input,
                filter={'source': doc["metadata"]['source']},
                k=self.fetch_k,
            )
            for (d, score) in documents:
                if d.metadata['type'] == 'data':
                    if "data" in d.metadata:
                        results[doc['metadata']['source']]['page_content'].append({
                            "content": d.metadata['data'],
                            "index": d.metadata['chunk_index'],
                            "score": score,
                        })
                    else:
                        results[doc['metadata']['source']]['page_content'].append({
                            "content": d.page_content,
                            "index": d.metadata['chunk_index'],
                            "score": score,
                        })
                elif d.metadata['type'] == 'document_summary':
                    results[doc['metadata']['source']]['page_content'].append({
                        "content": d.page_content,
                        "index": -1,
                        "score": score,
                    })
            if not results[doc['metadata']['source']]['page_content']:
                results.pop(doc['metadata']['source'])
        if len(results.keys()) >= self.top_k:
            break
    if self.document_debug:
        print_log("results =", results)
    _docs = []
    for value in results.values():
        _chunks = sorted(
            value['page_content'],
            key=lambda x: x["score"],
            reverse=not self.lower_score_better,
        )
        pages = list(map(lambda x: x['content'], _chunks))
        top_pages = pages[:self.page_top_k]
        if not top_pages:
            continue
        _docs.append(Document(
            page_content="\n\n".join(top_pages),
            metadata=value['metadata'],
        ))
    return _docs
```
This function organizes the documents by their source, performs additional similarity searches, and merges the results into a final list of documents.

### get_relevant_documents

This function retrieves the most relevant documents based on the input query. It takes the input query and a callback manager as input and returns a list of relevant documents.

Example:
```python
def get_relevant_documents(
    self,
    input: str,
    *,
    run_manager: CallbackManagerForRetrieverRun,
    **kwargs: Any,
) -> List[Document]:
    if not self.no_cleanse:
        test_docs = self.vectorstore.similarity_search_with_score(
            input,
            filter={"$and": [{"library": self.doc_library}, {"type": "data"}]},
            k=1,
        )
        if test_docs and "data" in test_docs[0][0].metadata:
            input = cleanse_data(input)
    if self.document_debug:
        print_log("using input =", input)
    docs = self.vectorstore.similarity_search_with_score(
        input,
        filter={'library': self.doc_library},
        k=self.fetch_k,
    )
    if self.document_debug:
        print_log("similarity_search =", docs)
    docs = self._rerank_documents(docs)
    if self.document_debug:
        print_log("rerank_documents =", docs)
    docs = self.merge_results(input, docs)
    if self.document_debug:
        print_log("merge_results =", docs)
    return docs
```
This function performs the entire process of cleansing the input, retrieving documents, reranking them, and merging the results to return the most relevant documents.

## Dependencies Used and Their Descriptions

### langchain_core.retrievers.BaseRetriever

This is the base class for all retrievers in the LangChain framework. It provides the basic structure and methods that all retrievers must implement.

### typing

This module provides support for type hints, which are used throughout the code to specify the expected types of variables and function parameters.

### langchain_core.documents.Document

This class represents a document in the LangChain framework. It is used to store the content and metadata of documents retrieved from the vector store.

### langchain_core.callbacks.CallbackManagerForRetrieverRun

This class manages callbacks for retriever runs, allowing for custom actions to be performed at various stages of the retrieval process.

### ..tools.log.print_log

This function is used for logging debug information. It prints the specified messages to the console or a log file.

### ..document_loaders.utils.cleanse_data

This function is used to cleanse the input data, removing any unwanted characters or formatting issues that could affect the retrieval process.

## Functional Flow

The functional flow of the `AlitaRetriever.py` file involves the following steps:

1. **Initialization:** The `AlitaRetriever` class is initialized with various parameters, including the vector store, document library, and weights for reranking.
2. **Input Cleansing:** The input query is optionally cleansed using the `cleanse_data` function.
3. **Similarity Search:** A similarity search is performed in the vector store to retrieve a list of documents and their scores.
4. **Reranking:** The retrieved documents are reranked based on their scores and predefined weights.
5. **Merging Results:** The reranked documents are merged to form the final set of relevant documents.
6. **Returning Documents:** The final set of relevant documents is returned to the caller.

Example:
```python
def get_relevant_documents(
    self,
    input: str,
    *,
    run_manager: CallbackManagerForRetrieverRun,
    **kwargs: Any,
) -> List[Document]:
    if not self.no_cleanse:
        test_docs = self.vectorstore.similarity_search_with_score(
            input,
            filter={"$and": [{"library": self.doc_library}, {"type": "data"}]},
            k=1,
        )
        if test_docs and "data" in test_docs[0][0].metadata:
            input = cleanse_data(input)
    if self.document_debug:
        print_log("using input =", input)
    docs = self.vectorstore.similarity_search_with_score(
        input,
        filter={'library': self.doc_library},
        k=self.fetch_k,
    )
    if self.document_debug:
        print_log("similarity_search =", docs)
    docs = self._rerank_documents(docs)
    if self.document_debug:
        print_log("rerank_documents =", docs)
    docs = self.merge_results(input, docs)
    if self.document_debug:
        print_log("merge_results =", docs)
    return docs
```
This example demonstrates the entire functional flow, from input cleansing to returning the final set of relevant documents.

## Endpoints Used/Created

The `AlitaRetriever.py` file does not explicitly define or call any endpoints. The primary interactions are with the vector store for performing similarity searches and retrieving documents.