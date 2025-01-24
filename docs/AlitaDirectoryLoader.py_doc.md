# AlitaDirectoryLoader.py

**Path:** `src/alita_sdk/langchain/document_loaders/AlitaDirectoryLoader.py`

## Data Flow

The data flow within the `AlitaDirectoryLoader.py` file is centered around the loading and processing of documents from a specified directory. The data originates from files within the directory specified by the user. These files are filtered based on their extensions, and only the relevant files are processed further. The data is then transformed into `Document` objects, which are subsequently returned or yielded by the loader.

The primary data elements include the file paths and the content of the files. The file paths are used to locate and identify the files, while the content is read and transformed into `Document` objects. The data flow can be summarized as follows:

1. **Initialization:** The loader is initialized with various parameters, including file extensions to include or exclude, and options for raw content and page splitting.
2. **File Filtering:** The files in the specified directory are filtered based on their extensions.
3. **File Processing:** The content of the filtered files is read and transformed into `Document` objects.
4. **Data Output:** The `Document` objects are either returned as a list or yielded one by one.

Example:
```python
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
```

## Functions Descriptions

### `__init__`

The `__init__` function initializes the `AlitaDirectoryLoader` with various parameters. It sets up the file extensions to include or exclude, and options for raw content and page splitting. It also removes these parameters from the `kwargs` dictionary and sets the `loader_cls` to `UnstructuredLoader`.

**Parameters:**
- `kwargs`: A dictionary of keyword arguments.

**Example:**
```python
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

### `load_file`

The `load_file` function processes a single file. It checks if the file should be included based on its extension and visibility. If the file is to be included, it reads the content and transforms it into `Document` objects.

**Parameters:**
- `item`: The file path.
- `path`: The directory path.
- `docs`: A list of documents to append to.
- `pbar`: A progress bar (optional).
- `retval`: A boolean indicating whether to return the documents (optional).

**Example:**
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

### `load`

The `load` function returns a list of `Document` objects by calling the `lazy_load` function.

**Example:**
```python
def load(self, *args, **kwargs) -> List[Document]:
    return list(self.lazy_load(*args, **kwargs))
```

### `lazy_load`

The `lazy_load` function iterates over the files in the specified directory and processes each file using the `load_file` function. It handles progress tracking and sampling of files.

**Example:**
```python
def lazy_load(self) -> Iterator[Document]:
    p = Path(self.path)
    if not p.exists():
        raise FileNotFoundError(f"Directory not found: '{self.path}'")
    if not p.is_dir():
        raise ValueError(f"Expected directory, got file: '{self.path}'")

    items = list(p.rglob(self.glob) if self.recursive else p.glob(self.glob))

    if self.sample_size > 0:
        if self.randomize_sample:
            randomizer = (
                random.Random(self.sample_seed) if self.sample_seed else random
            )
            randomizer.shuffle(items)  # type: ignore
        items = items[: min(len(items), self.sample_size)]

    pbar = None
    if self.show_progress:
        try:
            from tqdm import tqdm

            pbar = tqdm(total=len(items))
        except ImportError as e:
            logger.warning(
                "To log the progress of DirectoryLoader you need to install tqdm, "
                "`pip install tqdm`"
            )
            if self.silent_errors:
                logger.warning(e)
            else:
                raise ImportError(
                    "To log the progress of DirectoryLoader "
                    "you need to install tqdm, "
                    "`pip install tqdm`"
                )

    for i in items:
        for _ in self.load_file(i, p, [], pbar, retval=True):
            yield _

    if pbar:
        pbar.close()
```

## Dependencies Used and Their Descriptions

### `os`

The `os` module is used for interacting with the operating system, particularly for file and directory operations.

### `random`

The `random` module is used for randomizing the order of files when sampling.

### `logging`

The `logging` module is used for logging messages, warnings, and errors.

### `pathlib.Path`

The `Path` class from the `pathlib` module is used for handling file system paths in an object-oriented way.

### `typing`

The `typing` module is used for type hinting, providing better code readability and type checking.

### `langchain_community.document_loaders.DirectoryLoader`

The `DirectoryLoader` class from the `langchain_community.document_loaders` module is the base class for `AlitaDirectoryLoader`.

### `langchain_core.documents.Document`

The `Document` class from the `langchain_core.documents` module represents the documents being loaded and processed.

### `_is_visible`

The `_is_visible` function from the `langchain_community.document_loaders.directory` module is used to check if a file is visible.

### `UnstructuredLoader`

The `UnstructuredLoader` class from the `langchain_unstructured` module is used as the default loader class for processing files.

### `loaders_map`

The `loaders_map` from the `.constants` module is a dictionary mapping file extensions to their respective loader classes and arguments.

### `print_log`

The `print_log` function from the `..tools.log` module is used for printing log messages.

## Functional Flow

The functional flow of the `AlitaDirectoryLoader.py` file involves the following steps:

1. **Initialization:** The `AlitaDirectoryLoader` is initialized with various parameters, including file extensions to include or exclude, and options for raw content and page splitting.
2. **File Filtering:** The files in the specified directory are filtered based on their extensions.
3. **File Processing:** The content of the filtered files is read and transformed into `Document` objects using the appropriate loader class.
4. **Data Output:** The `Document` objects are either returned as a list or yielded one by one.

The process is initiated by calling the `load` or `lazy_load` function, which iterates over the files in the specified directory and processes each file using the `load_file` function. The progress of the file processing can be tracked using a progress bar if the `show_progress` option is enabled.

Example:
```python
def lazy_load(self) -> Iterator[Document]:
    p = Path(self.path)
    if not p.exists():
        raise FileNotFoundError(f"Directory not found: '{self.path}'")
    if not p.is_dir():
        raise ValueError(f"Expected directory, got file: '{self.path}'")

    items = list(p.rglob(self.glob) if self.recursive else p.glob(self.glob))

    if self.sample_size > 0:
        if self.randomize_sample:
            randomizer = (
                random.Random(self.sample_seed) if self.sample_seed else random
            )
            randomizer.shuffle(items)  # type: ignore
        items = items[: min(len(items), self.sample_size)]

    pbar = None
    if self.show_progress:
        try:
            from tqdm import tqdm

            pbar = tqdm(total=len(items))
        except ImportError as e:
            logger.warning(
                "To log the progress of DirectoryLoader you need to install tqdm, "
                "`pip install tqdm`"
            )
            if self.silent_errors:
                logger.warning(e)
            else:
                raise ImportError(
                    "To log the progress of DirectoryLoader "
                    "you need to install tqdm, "
                    "`pip install tqdm`"
                )

    for i in items:
        for _ in self.load_file(i, p, [], pbar, retval=True):
            yield _

    if pbar:
        pbar.close()
```

## Endpoints Used/Created

The `AlitaDirectoryLoader.py` file does not explicitly define or call any endpoints. Its primary focus is on loading and processing documents from a specified directory.