# indexer.py

**Path:** `src/alita_sdk/langchain/indexer.py`

## Data Flow

The data flow within `indexer.py` is structured to handle the indexing and searching of documents using various models and vector stores. The main function orchestrates the process, starting with loading data, extracting keywords, splitting data, and embedding the data into a vector store. The data originates from loaders, which fetch the raw data based on the provided parameters. This data is then processed through keyword extraction and splitting before being embedded using the specified embedding model. The embeddings are stored in a vector store, which is used for efficient retrieval and search operations. Intermediate variables such as `embedding`, `vectorstore`, and `vectoradapter` are used to manage the data transformations and storage. The data flow ensures that the documents are processed, indexed, and stored in a manner that allows for efficient searching and retrieval.

Example:
```python
embedding = get_embeddings(embedding_model, embedding_model_params)
vectorstore = get_vectorstore(vectorstore, vectorstore_params, embedding_func=embedding)
vectoradapter = VectorAdapter(
    vectorstore=vectorstore,
    embeddings=embedding,
    quota_params=quota_params,
)
```
In this example, the embedding model is used to generate embeddings for the data, which are then stored in a vector store. The `VectorAdapter` manages the interaction with the vector store, ensuring that the data is stored and retrieved efficiently.

## Functions Descriptions

### main

The `main` function is the core of the indexing process. It takes various parameters related to the dataset, models, and processing prompts. The function starts by importing necessary packages and checking for NLTK data. It then proceeds to load data using the specified loader, extract keywords, split the data, and generate embeddings. The embeddings are stored in a vector store, and the function ensures that the storage quota is not exceeded. The function also handles document processing prompts and chunk processing prompts, generating summaries and metadata as needed. The function supports multi-threading for parallel processing of documents.

### index

The `index` function is a wrapper around the `main` function. It takes the same parameters as `main` and simply calls `main` with those parameters. This function provides a simpler interface for indexing documents.

### search

The `search` function handles searching for documents based on chat history. It takes parameters related to the embedding model, vector store, and search configuration. The function retrieves the embeddings and vector store, and uses a retriever to search for relevant documents. The search results are returned along with references to the source documents.

### predict

The `predict` function generates predictions based on chat history and search results. It takes parameters related to the chat history, AI model, and search configuration. The function performs a search using the `search` function, and then generates a response using the specified AI model. The response and references to the source documents are returned.

### deduplicate

The `deduplicate` function handles deduplication of documents in the vector store. It takes parameters related to the embedding model, vector store, and deduplication configuration. The function retrieves the embeddings and vector store, and performs deduplication based on the specified cutoff score and function. The deduplication results are returned as pairs of similar documents and an Excel file with the deduplication report.

### delete

The `delete` function deletes documents from the vector store based on the specified dataset and library. It takes parameters related to the embedding model, vector store, and deletion configuration. The function retrieves the embeddings and vector store, and deletes the specified documents. The function ensures that the storage quota is checked before and after deletion.

## Dependencies Used and Their Descriptions

- `io`: Used for handling input and output operations, particularly for creating in-memory file objects.
- `os`: Used for interacting with the operating system, such as creating temporary directories and handling file paths.
- `json`: Used for parsing and generating JSON data.
- `hashlib`: Used for generating hash values for deduplication.
- `operator`: Used for performing comparison operations in deduplication.
- `tempfile`: Used for creating temporary files and directories.
- `threading`: Used for multi-threading support.
- `importlib`: Used for importing modules dynamically.
- `concurrent.futures`: Used for managing concurrent execution of tasks.
- `typing.Optional`: Used for type hinting optional parameters.
- `langchain_core.documents.Document`: Represents a document in the Langchain framework.
- `langchain.schema.HumanMessage`: Represents a human message in the Langchain framework.
- `langchain_core.interfaces.llm_processor`: Provides functions for processing with language models.
- `langchain_core.interfaces.loaders`: Provides functions for loading data.
- `langchain_core.interfaces.splitters.Splitter`: Provides functions for splitting data.
- `langchain_core.tools.log`: Provides logging functions.
- `langchain_core.tools.vector.VectorAdapter`: Manages interactions with vector stores.
- `langchain_core.tools.utils`: Provides utility functions such as source replacement and NLTK download.
- `langchain_core.retrievers.AlitaRetriever`: Provides a retriever for searching documents.
- `sentence_transformers.util`: Provides utility functions for sentence transformers.
- `openpyxl.Workbook`: Used for creating Excel workbooks.
- `torch`: Used for tensor operations in deduplication.
- `numpy`: Used for numerical operations in deduplication.
- `chromadb.utils.distance_functions`: Provides distance functions for similarity calculations.

## Functional Flow

The functional flow of `indexer.py` involves several key steps:
1. **Initialization**: The main function initializes by importing necessary packages and checking for NLTK data.
2. **Data Loading**: Data is loaded using the specified loader and parameters.
3. **Keyword Extraction**: Keywords are extracted from the loaded data using the specified keyword extractor.
4. **Data Splitting**: The data is split into chunks using the specified splitter and parameters.
5. **Embedding Generation**: Embeddings are generated for the data chunks using the specified embedding model.
6. **Vector Store Interaction**: The embeddings are stored in a vector store, and the function ensures that the storage quota is not exceeded.
7. **Document Processing**: Document processing prompts and chunk processing prompts are handled, generating summaries and metadata as needed.
8. **Multi-threading**: The function supports multi-threading for parallel processing of documents.
9. **Search and Prediction**: The search and predict functions handle searching for documents and generating predictions based on chat history and search results.
10. **Deduplication**: The deduplicate function handles deduplication of documents in the vector store based on the specified cutoff score and function.
11. **Deletion**: The delete function deletes documents from the vector store based on the specified dataset and library.

## Endpoints Used/Created

The `indexer.py` file does not explicitly define or call any external endpoints. The functionality is focused on processing and managing documents within the Langchain framework, using various models and vector stores for embedding and retrieval operations. The interactions are primarily internal, involving the loading, processing, and storing of data within the system.