# AlitaDirectoryLoader.py

**Path:** `src/alita_sdk/langchain/document_loaders/AlitaDirectoryLoader.py`

## Data Flow

The data flow within the `AlitaDirectoryLoader` class is primarily concerned with loading and processing files from a directory. The process begins with the initialization of the class, where various parameters are set based on the provided keyword arguments. These parameters include options for raw content, page splitting, and file extensions to include or exclude. The data flow can be summarized as follows:

1. **Initialization:** The `__init__` method sets up the loader with the specified parameters and initializes the superclass with the remaining arguments.
2. **File Loading:** The `load_file` method is responsible for loading individual files. It checks the file extension against the include and exclude lists, processes the file if it is visible, and uses the appropriate loader class to load the file's content.
3. **Directory Loading:** The `lazy_load` method iterates over the files in the specified directory, applying filters and loading each file using the `load_file` method. The `load` method simply converts the iterator returned by `lazy_load` into a list.

Example:
```python
class AlitaDirectoryLoader(DirectoryLoader):
    def __init__(self, **kwargs):
        self.raw_content = kwargs.get('table_raw_content', False)
        self.page_split = kwargs.get('docs_page_split', False)
        index_inclue_ext = kwargs.get('index_file_exts', '')
        index_exclude_ext = kwargs.get('index_exclude_file_exts', '')
        self.index_file_exts = [
            ext.strip()
            for ext in index_inclue_ext.split(",")
            if ext.strip()
        ]
        self.index_exclude_file_exts = [
            ext.strip()
            for ext in index_exclude_ext.split(",")
            if ext.strip()
        ]
        for key in ['table_raw_content', 'docs_page_split', 'index_file_exts', 'index_exclude_file_exts']:
            try:
                del kwargs[key]
            except:
                pass
        kwargs["loader_cls"] = UnstructuredLoader
        super().__init__(**kwargs)
```

## Functions Descriptions

### `__init__(self, **kwargs)`

The constructor method initializes the `AlitaDirectoryLoader` with various parameters. It sets up options for raw content, page splitting, and file extensions to include or exclude. It also initializes the superclass with the remaining arguments.

- **Parameters:**
  - `kwargs`: Keyword arguments for configuration.
- **Processing Logic:**
  - Sets up raw content and page splitting options.
  - Parses include and exclude file extensions.
  - Initializes the superclass with the remaining arguments.

### `load_file(self, item: Path, path: Path, docs: List[Document], pbar: Optional[Any], retval: Optional[bool] = False)`

This method loads an individual file, checking its extension against the include and exclude lists, and processes it if it is visible. It uses the appropriate loader class to load the file's content.

- **Parameters:**
  - `item`: File path.
  - `path`: Directory path.
  - `docs`: List of documents to append to.
  - `pbar`: Progress bar (optional).
  - `retval`: Return value flag (optional).
- **Processing Logic:**
  - Checks file extension against include and exclude lists.
  - Processes the file if it is visible.
  - Uses the appropriate loader class to load the file's content.

### `load(self, *args, **kwargs) -> List[Document]`

This method loads all files in the specified directory and returns a list of documents.

- **Parameters:**
  - `args`: Positional arguments.
  - `kwargs`: Keyword arguments.
- **Processing Logic:**
  - Converts the iterator returned by `lazy_load` into a list.

### `lazy_load(self) -> Iterator[Document]`

This method iterates over the files in the specified directory, applying filters and loading each file using the `load_file` method.

- **Processing Logic:**
  - Iterates over files in the directory.
  - Applies filters and loads each file using `load_file`.

## Dependencies Used and Their Descriptions

### `os`

The `os` module provides a way of using operating system-dependent functionality like reading or writing to the file system.

### `random`

The `random` module implements pseudo-random number generators for various distributions.

### `logging`

The `logging` module is used for tracking events that happen when some software runs. It is used here for logging exceptions and warnings.

### `pathlib.Path`

The `pathlib` module offers classes representing filesystem paths with semantics appropriate for different operating systems. The `Path` class is used for filesystem path manipulations.

### `typing`

The `typing` module provides runtime support for type hints. It is used for type annotations in the code.

### `langchain_community.document_loaders.DirectoryLoader`

This is the superclass from which `AlitaDirectoryLoader` inherits. It provides the basic functionality for loading documents from a directory.

### `langchain_core.documents.Document`

This module provides the `Document` class, which represents a document in the system.

### `langchain_community.document_loaders.directory._is_visible`

This function checks if a file is visible (i.e., not hidden).

### `langchain_unstructured.UnstructuredLoader`

This module provides the `UnstructuredLoader` class, which is used to load unstructured documents.

### `constants.loaders_map`

This module provides a mapping of file extensions to their respective loader classes and arguments.

### `tools.log.print_log`

This function is used for printing log messages.

## Functional Flow

The functional flow of the `AlitaDirectoryLoader` class involves the following steps:

1. **Initialization:** The class is initialized with various parameters for raw content, page splitting, and file extensions to include or exclude.
2. **File Loading:** The `load_file` method is called for each file in the directory. It checks the file extension, processes the file if it is visible, and uses the appropriate loader class to load the file's content.
3. **Directory Loading:** The `lazy_load` method iterates over the files in the specified directory, applying filters and loading each file using the `load_file` method. The `load` method converts the iterator returned by `lazy_load` into a list.

Example:
```python
def load_file(self, item: Path, path: Path, docs: List[Document], pbar: Optional[Any], retval: Optional[bool] = False):
    sub_docs = None
    _str_item = str(item)
    _, file_ext = os.path.splitext(_str_item)
    if item.is_file():
        if self.index_file_exts and file_ext not in self.index_file_exts:
            return None
        if self.index_exclude_file_exts and file_ext in self.index_exclude_file_exts:
            return None
        if _is_visible(item.relative_to(path)) or self.load_hidden:
            try:
                print_log(f"Processing file: {_str_item}")
                if file_ext in loaders_map.keys():
                    if 'raw_content' in loaders_map[file_ext]['kwargs'].keys():
                        loaders_map[file_ext]['kwargs']['raw_content'] = self.raw_content
                    if 'page_split' in loaders_map[file_ext]['kwargs'].keys():
                        loaders_map[file_ext]['kwargs']['page_split'] = self.page_split
                    try:
                        sub_docs = loaders_map[file_ext]['class'](_str_item, **loaders_map[file_ext]['kwargs']).load()
                        if not retval:
                            docs.extend(sub_docs)
                    except Exception as e:
                        logger.exception("Got first exception")
                        try:
                            sub_docs = self.loader_cls(str(item), **self.loader_kwargs).load()
                            if not retval:
                                docs.extend(sub_docs)
                        except:
                            logger.exception("Got second exception")
                else:
                    sub_docs = self.loader_cls(str(item), **self.loader_kwargs).load()
                    if not retval:
                        docs.extend(sub_docs)
            except Exception as e:
                if self.silent_errors:
                    logger.warning(f"Error loading file {str(item)}: {e}")
                else:
                    raise e
            finally:
                if pbar:
                    pbar.update(1)
            if retval:
                if sub_docs is not None:
                    for _ in sub_docs:
                        yield _
```

## Endpoints Used/Created

This file does not explicitly define or call any endpoints.