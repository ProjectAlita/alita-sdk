# vector.py

**Path:** `src/alita_sdk/langchain/tools/vector.py`

## Data Flow

The data flow within `vector.py` revolves around the `VectorAdapter` class, which serves as an interface to different vector stores. The data originates from the vector store instance passed to the `VectorAdapter` during initialization. This instance is stored in the `_vectorstore` attribute. The data is then manipulated through various methods such as `persist`, `vacuum`, `quota_check`, `delete_dataset`, `delete_library`, and `get_data`. These methods interact with the vector store to perform operations like saving, optimizing space, checking quotas, and retrieving or deleting data. The data flow is primarily unidirectional, moving from the vector store to the adapter and then being processed or returned based on the method called.

Example:
```python
class VectorAdapter:
    def __init__(self, vectorstore, embeddings=None, quota_params=None):
        self._vectorstore = vectorstore
        self._embeddings = embeddings
        self._quota_params = quota_params
        self._vs_cls_name = self._vectorstore.__class__.__name__
```
In this snippet, the vector store instance is passed to the `VectorAdapter` and stored in the `_vectorstore` attribute, initiating the data flow.

## Functions Descriptions

### `__init__`
The `__init__` method initializes the `VectorAdapter` with a vector store instance, optional embeddings, and quota parameters. It sets these as attributes and determines the class name of the vector store for later use.

### `vectorstore`
The `vectorstore` property returns the vector store instance.

### `embeddings`
The `embeddings` property returns the embeddings from the vector store if available, otherwise, it returns the embeddings passed during initialization.

### `persist`
The `persist` method saves or syncs the vector store if the vector store class name is `Chroma`.

### `vacuum`
The `vacuum` method optimizes space usage by trimming the vector store if the class name is `Chroma`.

### `quota_check`
The `quota_check` method checks the used space size of the vector store if the class name is `Chroma`. It can enforce quotas and provide verbose output.

### `delete_dataset`
The `delete_dataset` method deletes documents from the vector store based on the dataset name. It supports `Chroma` and `PGVector` vector stores.

### `delete_library`
The `delete_library` method deletes documents from the vector store based on the library name. It supports `Chroma` and `PGVector` vector stores.

### `get_data`
The `get_data` method retrieves data (documents and metadata) from the vector store based on specified conditions. It supports `Chroma` and `PGVector` vector stores.

### `_pgvector_get_data`
The `_pgvector_get_data` method is a helper function for retrieving data from a `PGVector` vector store. It constructs and executes a query based on the provided conditions.

### `_pgvector_delete_by_filter`
The `_pgvector_delete_by_filter` method is a helper function for deleting data from a `PGVector` vector store based on specified conditions.

## Dependencies Used and Their Descriptions

### `quota_check` and `sqlite_vacuum` from `.quota`
These functions are used for checking quota and optimizing SQLite databases, respectively.

### `log` from `.log`
This module is used for logging debug information.

### `Session` from `sqlalchemy.orm`
This is used for creating database sessions when interacting with `PGVector` vector stores.

## Functional Flow

1. **Initialization**: The `VectorAdapter` is initialized with a vector store, embeddings, and quota parameters.
2. **Property Access**: The `vectorstore` and `embeddings` properties provide access to the vector store and embeddings.
3. **Persistence**: The `persist` method saves the vector store if it is of type `Chroma`.
4. **Optimization**: The `vacuum` method optimizes the vector store if it is of type `Chroma`.
5. **Quota Checking**: The `quota_check` method checks the used space size and enforces quotas if the vector store is of type `Chroma`.
6. **Data Deletion**: The `delete_dataset` and `delete_library` methods delete documents from the vector store based on dataset or library names.
7. **Data Retrieval**: The `get_data` method retrieves documents and metadata from the vector store based on specified conditions.
8. **Helper Functions**: The `_pgvector_get_data` and `_pgvector_delete_by_filter` methods assist in data retrieval and deletion for `PGVector` vector stores.

## Endpoints Used/Created

This file does not explicitly define or call any endpoints. It primarily interacts with vector store instances and performs operations on them.