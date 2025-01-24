# vector.py

**Path:** `src/alita_sdk/langchain/tools/vector.py`

## Data Flow

The data flow within the `vector.py` file revolves around the `VectorAdapter` class, which serves as an adapter for different vector stores. The data originates from the initialization of the `VectorAdapter` class, where the vector store, embeddings, and quota parameters are passed as arguments. These data elements are stored as instance variables and are manipulated through various methods within the class.

For example, the `persist` method is used to save or sync the vector store if it is of type `Chroma`:

```python
    def persist(self):
        """ Save/sync/checkpoint vectorstore (if needed/supported) """
        if self._vs_cls_name == "Chroma":
            self._vectorstore.persist()
```

In this method, the data flow involves checking the class name of the vector store and calling the `persist` method on the vector store instance if the condition is met. This demonstrates how data is conditionally manipulated based on the type of vector store.

## Functions Descriptions

### `__init__`

The `__init__` method initializes the `VectorAdapter` class with the vector store, embeddings, and quota parameters. It sets these values as instance variables and determines the class name of the vector store.

### `vectorstore`

The `vectorstore` property method returns the vector store instance.

### `embeddings`

The `embeddings` property method returns the embeddings from the vector store if available; otherwise, it returns the embeddings passed during initialization.

### `persist`

The `persist` method saves or syncs the vector store if it is of type `Chroma`.

### `vacuum`

The `vacuum` method optimizes space usage by trimming the vector store if it is of type `Chroma`.

### `quota_check`

The `quota_check` method checks the used space size of the vector store if it is of type `Chroma`. It uses the `quota_check` function from the `quota` module.

### `delete_dataset`

The `delete_dataset` method deletes documents from the vector store based on the dataset name. It supports `Chroma` and `PGVector` vector stores.

### `delete_library`

The `delete_library` method deletes documents from the vector store based on the library name. It supports `Chroma` and `PGVector` vector stores.

### `get_data`

The `get_data` method retrieves data (documents and metadata) from the vector store based on the specified conditions. It supports `Chroma` and `PGVector` vector stores.

### `_pgvector_get_data`

The `_pgvector_get_data` method is a helper function that retrieves data from a `PGVector` vector store using SQLAlchemy sessions.

### `_pgvector_delete_by_filter`

The `_pgvector_delete_by_filter` method is a helper function that deletes data from a `PGVector` vector store based on the specified conditions using SQLAlchemy sessions.

## Dependencies Used and Their Descriptions

### `quota_check` and `sqlite_vacuum` from `quota`

These functions are used for checking the quota and optimizing space usage, respectively.

### `log`

The `log` module is used for logging debug information.

### `Session` from `sqlalchemy.orm`

The `Session` class from SQLAlchemy is used for managing database sessions when interacting with `PGVector` vector stores.

## Functional Flow

The functional flow of the `vector.py` file begins with the initialization of the `VectorAdapter` class, followed by the use of its methods to manipulate the vector store. The methods are conditionally executed based on the type of vector store, and they interact with the vector store to perform operations such as persisting data, optimizing space, checking quotas, deleting datasets or libraries, and retrieving data.

For example, the `delete_dataset` method follows this flow:

1. Check the class name of the vector store.
2. If the vector store is `Chroma`, delete documents based on the dataset name.
3. If the vector store is `PGVector`, use the `_pgvector_delete_by_filter` helper method to delete documents based on the dataset name.
4. Raise an error if the vector store type is unsupported.

## Endpoints Used/Created

The `vector.py` file does not explicitly define or call any endpoints. It primarily focuses on interacting with vector stores and performing operations on them based on their type.