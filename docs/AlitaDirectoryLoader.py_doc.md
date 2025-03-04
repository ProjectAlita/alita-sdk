# AlitaDirectoryLoader.py

**Path:** `src/alita_sdk/langchain/document_loaders/AlitaDirectoryLoader.py`

## Data Flow

The data flow within the `AlitaDirectoryLoader` class is structured to handle the loading and processing of files from a specified directory. The process begins with the initialization of the class, where various parameters are set based on the provided keyword arguments. These parameters include options for handling raw content, page splitting, and file extensions to include or exclude.

The primary method responsible for data flow is `load_file`, which takes a file path, directory path, a list of documents, and an optional progress bar as inputs. The method first checks if the file should be processed based on its extension and visibility. If the file meets the criteria, it is processed using the appropriate loader class from the `loaders_map` dictionary. The loaded documents are then appended to the provided list of documents.

The `load` method initiates the loading process by calling the `lazy_load` method, which iterates over the files in the specified directory and yields the loaded documents. This method also handles sampling and progress tracking if enabled.

### Example
```python
# Example of data flow in load_file method
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
                if 'is_multimodal_processing' in loaders_map[file_ext].keys() and loaders_map[file_ext]['is_multimodal_processing'] and self.llm:
                    loaders_map[file_ext]['kwargs']['llm'] = self.llm
                    loaders_map[file_ext]['kwargs']['prompt'] = self.prompt if self.prompt is not None else DEFAULT_MULTIMODAL_PROMPT
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
The `__init__` method initializes the `AlitaDirectoryLoader` class with various parameters. It sets options for handling raw content, page splitting, and file extensions to include or exclude. It also sets up the loader class and keyword arguments for processing files.

### `load_file`
The `load_file` method processes a single file. It checks if the file should be processed based on its extension and visibility. If the file meets the criteria, it is processed using the appropriate loader class from the `loaders_map` dictionary. The loaded documents are then appended to the provided list of documents.

### `load`
The `load` method initiates the loading process by calling the `lazy_load` method, which iterates over the files in the specified directory and yields the loaded documents.

### `lazy_load`
The `lazy_load` method iterates over the files in the specified directory and yields the loaded documents. It handles sampling and progress tracking if enabled.

## Dependencies Used and Their Descriptions

### `os`
The `os` module is used for interacting with the operating system, including file and directory operations.

### `random`
The `random` module is used for randomizing the order of files when sampling.

### `logging`
The `logging` module is used for logging messages and exceptions.

### `pathlib.Path`
The `pathlib.Path` class is used for handling file system paths in an object-oriented manner.

### `langchain_community.document_loaders.DirectoryLoader`
The `DirectoryLoader` class from the `langchain_community.document_loaders` module is the base class for `AlitaDirectoryLoader`.

### `langchain_core.documents.Document`
The `Document` class from the `langchain_core.documents` module represents a document loaded from a file.

### `_is_visible`
The `_is_visible` function from the `langchain_community.document_loaders.directory` module checks if a file is visible.

### `UnstructuredLoader`
The `UnstructuredLoader` class from the `langchain_unstructured` module is used for loading unstructured documents.

### `loaders_map`
The `loaders_map` dictionary from the `.constants` module maps file extensions to loader classes and their keyword arguments.

### `DEFAULT_MULTIMODAL_PROMPT`
The `DEFAULT_MULTIMODAL_PROMPT` constant from the `..constants` module is used as the default prompt for multimodal processing.

### `print_log`
The `print_log` function from the `..tools.log` module is used for printing log messages.

## Functional Flow

The functional flow of the `AlitaDirectoryLoader` class begins with the initialization of the class, where various parameters are set based on the provided keyword arguments. The `load` method is then called to initiate the loading process. This method calls the `lazy_load` method, which iterates over the files in the specified directory and yields the loaded documents.

The `load_file` method is called for each file to be processed. It checks if the file should be processed based on its extension and visibility. If the file meets the criteria, it is processed using the appropriate loader class from the `loaders_map` dictionary. The loaded documents are then appended to the provided list of documents.

### Example
```python
# Example of functional flow in lazy_load method
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

The `AlitaDirectoryLoader` class does not explicitly define or call any endpoints. It primarily focuses on loading and processing files from a specified directory.