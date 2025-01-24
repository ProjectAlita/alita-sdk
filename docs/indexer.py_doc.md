# indexer.py

**Path:** `src/alita_sdk/langchain/indexer.py`

## Data Flow

The data flow within `indexer.py` is structured to handle the loading, processing, and indexing of documents. The process begins with the `main` function, which orchestrates the entire workflow. Data is initially loaded using a specified loader, which retrieves documents based on the provided parameters. These documents are then processed to extract keywords and summaries, which are subsequently embedded using a specified embedding model. The embeddings are stored in a vector store, which facilitates efficient retrieval and search operations.

A key aspect of the data flow is the use of intermediate variables and temporary storage. For instance, the `vectoradapter` object is used to manage interactions with the vector store, including adding documents and checking storage quotas. The `kw_extractor` object is used to extract keywords from documents, while the `llmodel` object is used for generating summaries and other AI-driven processing tasks.

Here is an example of a key data transformation:

```python
embedding = get_embeddings(embedding_model, embedding_model_params)
vectorstore = get_vectorstore(vectorstore, vectorstore_params, embedding_func=embedding)
vectoradapter = VectorAdapter(
    vectorstore=vectorstore,
    embeddings=embedding,
    quota_params=quota_params,
)
```

In this snippet, the embedding model is used to generate embeddings, which are then used to initialize the vector store and the `VectorAdapter` object. This setup is crucial for subsequent data processing and storage operations.

## Functions Descriptions

### `main`

The `main` function is the central orchestrator of the indexing process. It takes various parameters related to data loading, processing, and storage. The function initializes the embedding model and vector store, sets up the keyword extractor and AI model, and manages the overall workflow of loading, processing, and indexing documents. It also handles storage quota checks and manages temporary storage for document metadata.

### `index`

The `index` function is a wrapper around the `main` function, providing a simplified interface for indexing documents. It takes the same parameters as `main` and simply calls `main` with these parameters.

### `search`

The `search` function handles the retrieval of documents based on a given chat history. It initializes the embedding model and vector store, sets up the retriever, and performs a search operation to find the most relevant documents. The function returns the content of the top documents and their references.

### `predict`

The `predict` function generates a prediction based on the chat history and the results of a RAG (Retrieval-Augmented Generation) search. It combines the search results with additional context and guidance messages, and uses an AI model to generate a response. The function supports streaming responses and can return monitoring data if required.

### `deduplicate`

The `deduplicate` function handles the deduplication of documents in the vector store. It uses various scoring functions to identify and remove duplicate documents based on their embeddings. The function generates a report of the deduplication process, including a preview of the identified duplicates and an Excel file with detailed information.

### `delete`

The `delete` function removes documents from the vector store based on the specified dataset and library. It performs storage quota checks before and after the deletion process, and ensures that the vector store is properly vacuumed and persisted.

## Dependencies Used and Their Descriptions

The `indexer.py` file relies on several dependencies, including:

- `langchain_core.documents.Document`: Used for representing documents.
- `langchain.schema.HumanMessage`: Used for handling chat messages.
- Various modules from `interfaces` and `tools`: These include loaders, keyword extractors, splitters, LLM processors, and utility functions that facilitate the loading, processing, and indexing of documents.
- `VectorAdapter`: A custom class used for managing interactions with the vector store.
- `AlitaRetriever`: A custom retriever class used for searching documents in the vector store.

These dependencies are crucial for the functionality of the `indexer.py` file, providing the necessary tools and interfaces for document processing and indexing.

## Functional Flow

The functional flow of `indexer.py` begins with the initialization of the embedding model and vector store. The `main` function orchestrates the workflow, starting with the loading of documents using the specified loader. The documents are then processed to extract keywords and summaries, which are embedded and stored in the vector store. The function also handles storage quota checks and manages temporary storage for document metadata.

The `index` function provides a simplified interface for indexing documents, while the `search` function handles the retrieval of documents based on chat history. The `predict` function generates predictions based on the search results and additional context, and the `deduplicate` function handles the removal of duplicate documents from the vector store. The `delete` function removes documents based on the specified dataset and library.

## Endpoints Used/Created

The `indexer.py` file does not explicitly define or call any endpoints. However, it interacts with various components such as the vector store and AI models, which may involve underlying API calls or interactions with external services. The specific details of these interactions are abstracted away by the utility functions and classes used in the file.