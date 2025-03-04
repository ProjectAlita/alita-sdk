# AlitaDirectoryLoader.py

**Path:** `src/alita_sdk/langchain/document_loaders/AlitaDirectoryLoader.py`

## Data Flow

The data flow within the `AlitaDirectoryLoader.py` file begins with the initialization of the `AlitaDirectoryLoader` class, which inherits from the `DirectoryLoader` class. The class constructor (`__init__`) sets up various parameters such as `raw_content`, `page_split`, `index_file_exts`, `index_exclude_file_exts`, `llm`, and `prompt`. These parameters are used to configure the behavior of the loader, including filtering documents by file extensions and setting up multimodal processing with a language model (LLM).

The primary data flow occurs in the `load_file` method, which processes individual files within a directory. The method checks if a file should be included or excluded based on its extension and visibility. If the file is to be processed, it uses the appropriate loader from the `loaders_map` to load the document's content. The loaded content is then appended to the `docs` list or yielded if the `retval` parameter is set to `True`.

The `load` method initiates the loading process by calling the `lazy_load` method, which iterates over the files in the specified directory and processes each file using the `load_file` method. The `lazy_load` method also handles sampling and progress tracking using the `tqdm` library.

Example:
```python
class AlitaDirectoryLoader(DirectoryLoader):
    def __init__(self, **kwargs):
        self.raw_content = kwargs.get('table_raw_content', False)
        self.page_split = kwargs.get('docs_page_split', False)
        # Initialization code...
        super().__init__(**kwargs)

    def load_file(self, item: Path, path: Path, docs: List[Document], pbar: Optional[Any], retval: Optional[bool] = False):
        # File loading code...
        if item.is_file():
            if self.index_file_exts and file_ext not in self.index_file_exts:
                return None
            # More processing code...
            docs.extend(sub_docs)
```

## Functions Descriptions

### `__init__(self, **kwargs)`

The constructor initializes the `AlitaDirectoryLoader` with various parameters. It sets up the `raw_content`, `page_split`, `index_file_exts`, `index_exclude_file_exts`, `llm`, and `prompt` attributes based on the provided keyword arguments. It also configures the loader class to use `UnstructuredLoader` and calls the parent class's constructor.

### `load_file(self, item: Path, path: Path, docs: List[Document], pbar: Optional[Any], retval: Optional[bool] = False)`

This method processes a single file. It checks if the file should be included or excluded based on its extension and visibility. If the file is to be processed, it uses the appropriate loader from the `loaders_map` to load the document's content. The loaded content is then appended to the `docs` list or yielded if the `retval` parameter is set to `True`.

### `load(self, *args, **kwargs) -> List[Document]`

This method initiates the loading process by calling the `lazy_load` method and returning the loaded documents as a list.

### `lazy_load(self) -> Iterator[Document]`

This method iterates over the files in the specified directory and processes each file using the `load_file` method. It handles sampling and progress tracking using the `tqdm` library.

## Dependencies Used and Their Descriptions

### `os`

Used for interacting with the operating system, such as checking file extensions and paths.

### `random`

Used for randomizing the order of files when sampling.

### `logging`

Used for logging messages and exceptions.

### `pathlib.Path`

Used for handling file system paths in an object-oriented manner.

### `typing`

Provides type hints for better code readability and type checking.

### `langchain_community.document_loaders.DirectoryLoader`

The parent class that `AlitaDirectoryLoader` inherits from, providing core directory loading functionality.

### `langchain_core.documents.Document`

Represents a document object that is loaded and processed.

### `langchain_community.document_loaders.directory._is_visible`

A helper function to check if a file is visible.

### `langchain_unstructured.UnstructuredLoader`

The default loader class used for loading unstructured documents.

### `loaders_map`

A mapping of file extensions to their respective loader classes and configurations.

### `DEFAULT_MULTIMODAL_PROMPT`

A default prompt used for multimodal processing with an LLM.

### `print_log`

A helper function for printing log messages.

## Functional Flow

1. **Initialization**: The `AlitaDirectoryLoader` class is initialized with various parameters, setting up the loader's behavior.
2. **Loading Files**: The `load` method is called, which in turn calls the `lazy_load` method to iterate over files in the directory.
3. **Processing Files**: The `load_file` method processes each file, checking its extension and visibility, and using the appropriate loader to load its content.
4. **Appending Documents**: The loaded content is appended to the `docs` list or yielded if the `retval` parameter is set to `True`.
5. **Progress Tracking**: The `tqdm` library is used to track the progress of file loading if enabled.

## Endpoints Used/Created

This file does not explicitly define or call any endpoints. It focuses on loading and processing documents from a directory.