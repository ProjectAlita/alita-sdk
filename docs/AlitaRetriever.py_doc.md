# AlitaRetriever.py

**Path:** `src/alita_sdk/langchain/retrievers/AlitaRetriever.py`

## Data Flow

The data flow within the `AlitaRetriever.py` file is centered around the retrieval and processing of documents from a vector store. The data originates from the input query provided by the user, which is then processed and used to search for similar documents in the vector store. The retrieved documents are then reranked and merged based on specific criteria before being returned as the final output.

For example, in the `get_relevant_documents` function, the input query is first cleansed (if necessary) and then used to perform a similarity search in the vector store. The retrieved documents are then reranked using the `_rerank_documents` function and merged using the `merge_results` function.

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

# Process
#
        docs = self.vectorstore.similarity_search_with_score(
            input,
            filter={'library': self.doc_library},
            k=self.fetch_k,
        )
```

## Functions Descriptions

### _rerank_documents

This function reranks the retrieved documents based on their scores and predefined weights. It takes a list of tuples (documents and their scores) as input and returns a sorted list of documents with updated scores.

**Example:**

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

### merge_results

This function merges the results from the similarity search based on the input query and the retrieved documents. It organizes the documents by their source and returns a list of merged documents.

**Example:**

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

This function retrieves the most relevant documents based on the input query. It performs a similarity search, reranks the documents, and merges the results before returning the final list of documents.

**Example:**

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

This is the base class for all retrievers in the LangChain framework. It provides the basic structure and methods that all retrievers must implement.

### typing

The `typing` module is used for type hints and annotations, which help in understanding the expected input and output types of functions.

### langchain_core.documents.Document

This class represents a document in the LangChain framework. It contains the content and metadata of a document.

### langchain_core.callbacks.CallbackManagerForRetrieverRun

This class manages callbacks for retriever runs, allowing for custom actions to be performed during the retrieval process.

### ..tools.log.print_log

This function is used for logging debug information during the retrieval process.

### ..document_loaders.utils.cleanse_data

This function is used to cleanse the input data before performing the similarity search.

## Functional Flow

The functional flow of the `AlitaRetriever.py` file involves the following steps:

1. **Initialization:** The `AlitaRetriever` class is initialized with the necessary parameters, including the vector store, document library, and various configuration options.
2. **Input Cleansing:** If required, the input query is cleansed using the `cleanse_data` function.
3. **Similarity Search:** The cleansed input query is used to perform a similarity search in the vector store to retrieve relevant documents.
4. **Reranking:** The retrieved documents are reranked based on their scores and predefined weights using the `_rerank_documents` function.
5. **Merging Results:** The reranked documents are merged based on their source and organized into a final list of documents using the `merge_results` function.
6. **Returning Results:** The final list of relevant documents is returned as the output.

## Endpoints Used/Created

There are no explicit endpoints used or created in the `AlitaRetriever.py` file. The functionality is focused on retrieving and processing documents from a vector store based on the input query.
