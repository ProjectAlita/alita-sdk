# AlitaRetriever.py

**Path:** `src/alita_sdk/langchain/retrievers/AlitaRetriever.py`

## Data Flow

The data flow within the `AlitaRetriever.py` file is centered around the retrieval and processing of documents from a vector store. The data originates from user input, which is then processed and used to query the vector store for relevant documents. These documents are then reranked and merged to produce the final output.

For example, in the `get_relevant_documents` function, the input data is first cleansed (if necessary) and then used to perform a similarity search in the vector store. The retrieved documents are then reranked based on their scores and merged to form the final list of relevant documents.

```python
# Example of data flow in get_relevant_documents function
if not self.no_cleanse:
    test_docs = self.vectorstore.similarity_search_with_score(
        input,
        filter={"$and": [{"library": self.doc_library}, {"type": "data"}]},
        k=1,
    )
    if test_docs and "data" in test_docs[0][0].metadata:
        input = cleanse_data(input)

# Perform similarity search
if self.document_debug:
    print_log("using input =", input)
docs = self.vectorstore.similarity_search_with_score(
    input,
    filter={'library': self.doc_library},
    k=self.fetch_k,
)

# Rerank documents
if self.document_debug:
    print_log("similarity_search =", docs)
docs = self._rerank_documents(docs)

# Merge results
if self.document_debug:
    print_log("rerank_documents =", docs)
docs = self.merge_results(input, docs)

# Final output
if self.document_debug:
    print_log("merge_results =", docs)
return docs
```

## Functions Descriptions

### _rerank_documents

The `_rerank_documents` function is responsible for reranking the retrieved documents based on their scores and predefined weights. It takes a list of tuples (documents and their scores) as input and returns a sorted list of documents.

```python
def _rerank_documents(self, documents: List[tuple]):
    """ Rerank documents """
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

### merge_results

The `merge_results` function merges the results from the similarity search and reranks them. It takes the input string and a list of document dictionaries as input and returns a list of `Document` objects.

```python
def merge_results(self, input:str, docs: List[dict]):
    results = {}
    for doc in docs:
        if doc['metadata']['source'] not in results.keys():
            results[doc['metadata']['source']] = {
                'page_content': [],
                'metadata': {
                    'source' : doc['metadata']['source'],
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

### get_relevant_documents

The `get_relevant_documents` function retrieves and processes relevant documents based on the input string. It performs a similarity search, reranks the documents, and merges the results to produce the final output.

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

## Dependencies Used and Their Descriptions

### langchain_core.retrievers.BaseRetriever

The `BaseRetriever` class from the `langchain_core.retrievers` module is the base class for the `AlitaRetriever` class. It provides the basic structure and functionality for a retriever.

### typing

The `typing` module is used for type hinting in the code. It helps in specifying the expected types of variables, function parameters, and return values.

### langchain_core.documents.Document

The `Document` class from the `langchain_core.documents` module is used to represent documents in the code. It contains the content and metadata of a document.

### langchain_core.callbacks.CallbackManagerForRetrieverRun

The `CallbackManagerForRetrieverRun` class from the `langchain_core.callbacks` module is used to manage callbacks during the retriever run.

### ..tools.log.print_log

The `print_log` function from the `..tools.log` module is used for logging debug information in the code.

### ..document_loaders.utils.cleanse_data

The `cleanse_data` function from the `..document_loaders.utils` module is used to cleanse the input data before processing.

## Functional Flow

The functional flow of the `AlitaRetriever.py` file involves the following steps:

1. **Initialization**: The `AlitaRetriever` class is initialized with the necessary parameters such as `vectorstore`, `doc_library`, `top_k`, etc.
2. **Data Cleansing**: The input data is cleansed if the `no_cleanse` flag is not set.
3. **Similarity Search**: A similarity search is performed in the vector store to retrieve relevant documents based on the input data.
4. **Reranking**: The retrieved documents are reranked based on their scores and predefined weights.
5. **Merging Results**: The reranked documents are merged to form the final list of relevant documents.
6. **Output**: The final list of relevant documents is returned as the output.

## Endpoints Used/Created

The `AlitaRetriever.py` file does not explicitly define or call any endpoints. The primary interaction is with the vector store for performing similarity searches and retrieving documents.