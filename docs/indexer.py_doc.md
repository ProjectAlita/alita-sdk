# indexer.py

**Path:** `src/alita_sdk/langchain/indexer.py`

## Data Flow

The data flow within `indexer.py` is structured to handle the loading, processing, and indexing of documents. The process begins with the `main` function, which orchestrates the entire workflow. Data is initially loaded using a specified loader, which retrieves documents based on the provided parameters. These documents are then processed to extract keywords and summaries, which are added to the document metadata. The documents are subsequently split into chunks, and embeddings are generated for these chunks. Finally, the processed documents and their embeddings are added to a vector store for efficient retrieval.

Example:
```python
for document in loader(loader_name, loader_params, load_params):
    replace_source(document, source_replacers, keys=["source", "table_source"])
    if document_processing_prompt:
        document = summarize(llmodel, document, document_processing_prompt)
    if kw_for_document and kw_extractor.extractor:
        document.metadata['keywords'] = kw_extractor.extract_keywords(
            document.metadata.get('document_summary', '') + '\n' + document.page_content
        )
    splitter = Splitter(**splitter_params)
    for index, document in enumerate(splitter.split(document, splitter_name)):
        _documents.append(Document(
            page_content=document.page_content,
            metadata={
                'source': document.metadata['source'],
                'type': 'data',
                'library': library,
                'source_type': loader_name,
                'dataset': dataset,
                'chunk_index': index,
            }
        ))
```
This snippet shows the loading, processing, and splitting of documents, with metadata being updated at each step.

## Functions Descriptions

### `main`
The `main` function is the core of the indexing process. It initializes various components such as the embedding model, vector store, and keyword extractor. It then iterates over the documents loaded by the specified loader, processes each document to extract keywords and summaries, splits the documents into chunks, and generates embeddings for these chunks. The processed documents and their embeddings are then added to the vector store.

### `index`
The `index` function is a wrapper around the `main` function, providing a simplified interface for indexing documents. It accepts the same parameters as `main` and simply calls `main` with these parameters.

### `search`
The `search` function performs a search for documents based on a given chat history. It initializes the embedding model and vector store, and uses a retriever to find the most relevant documents. The function returns the content of the top documents and their references.

### `predict`
The `predict` function generates a prediction based on the chat history and the results of a search. It first performs a search to retrieve relevant documents, then uses an AI model to generate a response based on the chat history and the retrieved documents. The function returns the generated response and references to the documents used.

### `deduplicate`
The `deduplicate` function identifies and removes duplicate documents from the vector store. It uses embeddings to compare documents and determine their similarity. The function returns a list of duplicate document pairs and an Excel file containing the deduplication results.

### `delete`
The `delete` function removes documents from the vector store based on the specified dataset or library. It performs a quota check before and after the deletion to ensure that the storage quota is not exceeded.

## Dependencies Used and Their Descriptions

- `io`, `os`, `json`, `hashlib`, `operator`, `importlib`, `tempfile`: Standard Python libraries used for file and data manipulation, hashing, dynamic imports, and temporary file creation.
- `langchain_core.documents.Document`, `langchain.schema.HumanMessage`: Langchain components for handling documents and chat messages.
- `loader`, `KWextractor`, `Splitter`, `get_embeddings`, `summarize`, `get_model`, `get_vectorstore`, `add_documents`, `generateResponse`, `llm_predict`: Interfaces and tools for loading data, extracting keywords, splitting documents, generating embeddings, summarizing content, and interacting with AI models and vector stores.
- `unpack_json`, `download_nltk`, `replace_source`: Utility functions for JSON manipulation, downloading NLTK data, and replacing document sources.
- `VectorAdapter`: A tool for adapting vector stores to the required format.
- `print_log`, `log`: Logging utilities for debugging and information output.
- `AlitaRetriever`: A custom retriever for finding relevant documents in the vector store.
- `openpyxl`: A library for creating and manipulating Excel files.
- `sentence_transformers.util`: A library for computing similarity scores between embeddings.
- `chromadb.utils.distance_functions`: Utility functions for computing distances between vectors.

## Functional Flow

The functional flow of `indexer.py` starts with the `main` function, which initializes the necessary components and performs a series of steps to load, process, and index documents. The `index` function serves as a wrapper for `main`, providing a simplified interface. The `search` function retrieves relevant documents based on a chat history, while the `predict` function generates a response based on the search results. The `deduplicate` function identifies and removes duplicate documents, and the `delete` function removes documents from the vector store.

Example:
```python
embedding = get_embeddings(embedding_model, embedding_model_params)
vectorstore = get_vectorstore(vectorstore, vectorstore_params, embedding_func=embedding)
vectoradapter = VectorAdapter(
    vectorstore=vectorstore,
    embeddings=embedding,
)
for document in loader(loader_name, loader_params, load_params):
    replace_source(document, source_replacers, keys=["source", "table_source"])
    if document_processing_prompt:
        document = summarize(llmodel, document, document_processing_prompt)
    if kw_for_document and kw_extractor.extractor:
        document.metadata['keywords'] = kw_extractor.extract_keywords(
            document.metadata.get('document_summary', '') + '\n' + document.page_content
        )
    splitter = Splitter(**splitter_params)
    for index, document in enumerate(splitter.split(document, splitter_name)):
        _documents.append(Document(
            page_content=document.page_content,
            metadata={
                'source': document.metadata['source'],
                'type': 'data',
                'library': library,
                'source_type': loader_name,
                'dataset': dataset,
                'chunk_index': index,
            }
        ))
```
This snippet demonstrates the initialization of components and the processing of documents within the `main` function.

## Endpoints Used/Created

The `indexer.py` file does not explicitly define or call any endpoints. However, it interacts with various components and tools to load, process, and index documents, as well as to perform searches and generate predictions based on chat history.