# VectorstoreRetriever.py

**Path:** `src/alita_sdk/langchain/retrievers/VectorstoreRetriever.py`

## Data Flow

The data flow within the `VectorstoreRetriever.py` file revolves around retrieving relevant documents from a vector store based on an input query. The process begins with the `get_relevant_documents` method, which takes an input string and a run manager as parameters. This method utilizes the `vectorstore` instance to create a retriever object configured with specific search parameters, such as the number of documents to return (`top_k`) and a filter based on the document library (`doc_library`). The retriever then fetches the relevant documents, which are subsequently processed to extract and assign the `data` field from the document metadata to the `page_content` attribute of each document. The final list of processed documents is then returned as the output.

Example:
```python
vs_retriever = self.vectorstore.as_retriever(
    search_kwargs={
        "k": self.top_k,
        "filter": {
            "library": self.doc_library,
        },
    },
)
docs = vs_retriever.get_relevant_documents(input)
for doc in docs:
    if "data" in doc.metadata:
        doc.page_content = doc.metadata.pop("data")
```
In this example, the retriever is configured to fetch the top `k` documents from the specified document library, and the `data` field from the document metadata is assigned to the `page_content` attribute.

## Functions Descriptions

### `get_relevant_documents`

This function is responsible for retrieving relevant documents from the vector store based on the input query. It takes the following parameters:
- `input` (str): The input query string.
- `run_manager` (CallbackManagerForRetrieverRun): The run manager for handling callbacks during the retrieval process.
- `**kwargs` (Any): Additional keyword arguments.

The function creates a retriever object from the `vectorstore` instance, configured with search parameters such as the number of documents to return (`top_k`) and a filter based on the document library (`doc_library`). It then fetches the relevant documents using the retriever and processes each document to extract and assign the `data` field from the document metadata to the `page_content` attribute. The final list of processed documents is returned.

Example:
```python
def get_relevant_documents(
    self,
    input: str,
    *,
    run_manager: CallbackManagerForRetrieverRun,
    **kwargs: Any,
) -> List[Document]:
    vs_retriever = self.vectorstore.as_retriever(
        search_kwargs={
            "k": self.top_k,
            "filter": {
                "library": self.doc_library,
            },
        },
    )
    docs = vs_retriever.get_relevant_documents(input)
    for doc in docs:
        if "data" in doc.metadata:
            doc.page_content = doc.metadata.pop("data")
    return docs
```
In this example, the function retrieves the top `k` documents from the specified document library and processes each document to assign the `data` field to the `page_content` attribute.

## Dependencies Used and Their Descriptions

### `langchain_core.retrievers`

The `BaseRetriever` class from the `langchain_core.retrievers` module is imported and extended by the `VectorstoreRetriever` class. This base class provides the foundational structure and methods for creating custom retrievers.

### `typing`

The `Any`, `Dict`, `List`, and `Optional` types from the `typing` module are used for type hinting and annotations, ensuring that the function parameters and return types are clearly defined.

### `langchain_core.callbacks.manager`

The `Callbacks` and `CallbackManagerForRetrieverRun` classes from the `langchain_core.callbacks.manager` module are used to manage and handle callbacks during the document retrieval process.

### `langchain_core.documents`

The `Document` class from the `langchain_core.documents` module is used to represent the documents retrieved from the vector store. Each document contains metadata and content that are processed and returned by the retriever.

## Functional Flow

The functional flow of the `VectorstoreRetriever.py` file involves the following steps:
1. The `get_relevant_documents` method is called with an input query and a run manager.
2. A retriever object is created from the `vectorstore` instance, configured with search parameters such as the number of documents to return (`top_k`) and a filter based on the document library (`doc_library`).
3. The retriever fetches the relevant documents based on the input query.
4. Each retrieved document is processed to extract and assign the `data` field from the document metadata to the `page_content` attribute.
5. The final list of processed documents is returned as the output.

Example:
```python
def get_relevant_documents(
    self,
    input: str,
    *,
    run_manager: CallbackManagerForRetrieverRun,
    **kwargs: Any,
) -> List[Document]:
    vs_retriever = self.vectorstore.as_retriever(
        search_kwargs={
            "k": self.top_k,
            "filter": {
                "library": self.doc_library,
            },
        },
    )
    docs = vs_retriever.get_relevant_documents(input)
    for doc in docs:
        if "data" in doc.metadata:
            doc.page_content = doc.metadata.pop("data")
    return docs
```
In this example, the function retrieves the top `k` documents from the specified document library and processes each document to assign the `data` field to the `page_content` attribute.

## Endpoints Used/Created

The `VectorstoreRetriever.py` file does not explicitly define or call any endpoints. The primary functionality revolves around retrieving relevant documents from a vector store based on an input query.