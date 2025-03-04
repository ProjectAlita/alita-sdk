# loaders.py

**Path:** `src/alita_sdk/langchain/interfaces/loaders.py`

## Data Flow

The data flow within `loaders.py` revolves around the initialization and utilization of various document loaders. The primary data elements are the loader classes and the documents they process. The data originates from the loader classes defined in the `ex_classes` dictionary and the `langchain_community.document_loaders` module. These loaders transform raw data into structured documents through methods like `load`, `load_and_split`, and `lazy_load`.

For example, the `LoaderInterface` class initializes a loader based on the provided `loader_name` and parameters:

```python
class LoaderInterface:
    def __init__(self, loader_name, **kwargs):
        self.loader = LoaderInterface.get_loader_cls(loader_name)(**kwargs)
```

This snippet shows the initialization of a loader, where `loader_name` determines the specific loader class to be used. The data is then processed by calling methods on the `self.loader` instance.

## Functions Descriptions

### LoaderInterface

The `LoaderInterface` class serves as a wrapper for different loader classes. It initializes the appropriate loader based on the `loader_name` and provides methods to load data.

- **`__init__(self, loader_name, **kwargs)`**: Initializes the loader based on `loader_name` and additional parameters.
- **`get_loader_cls(loader_name)`**: A static method that returns the loader class corresponding to `loader_name`.
- **`load(self, *args, **kwargs)`**: Calls the `load` method of the initialized loader.
- **`load_and_split(self, *args, **kwargs)`**: Calls the `load_and_split` method of the initialized loader.
- **`lazy_load(self, *args, **kwargs)`**: Calls the `lazy_load` method of the initialized loader.

### get_data

The `get_data` function attempts to lazily load data using the provided loader. If lazy loading is not implemented, it falls back to the regular `load` method.

```python
def get_data(loader, load_params):
    if not load_params:
        load_params = {}
    try:
        doc_loader = loader.lazy_load(**load_params)
    except (NotImplementedError, TypeError):
        doc_loader = loader.load(**load_params)
    for _ in doc_loader:
        yield _
    return
```

### loader

The `loader` function initializes a `LoaderInterface` instance and yields documents loaded by the specified loader.

```python
def loader(loader_name, loader_params, load_params):
    loader_params = loader_params.copy()
    if loader_name == "ExcelLoader":
        loader_params.pop("autodetect_encoding", None)
        loader_params.pop("encoding", None)
    if loader_params.get('loader_cls'):
        loader_cls = LoaderInterface.get_loader_cls(loader_params.get('loader_cls'))
        loader_params['loader_cls'] = loader_cls
    loader = LoaderInterface(loader_name, **loader_params)
    for document in get_data(loader, load_params):
        yield document
```

## Dependencies Used and Their Descriptions

### langchain_community.document_loaders

This module provides various document loader classes used to process different types of data. The `loaders.py` file imports all available loaders from this module and uses them to initialize specific loader instances.

### AlitaQTestApiDataLoader, AlitaCSVLoader, AlitaExcelLoader, AlitaDirectoryLoader, AlitaGitRepoLoader, AlitaConfluenceLoader, BDDScenariosLoader

These are custom loader classes defined in the `document_loaders` package. They handle specific data sources like QTest API, CSV files, Excel files, directories, Git repositories, Confluence, and BDD scenarios.

## Functional Flow

The functional flow in `loaders.py` begins with the initialization of a `LoaderInterface` instance. The `loader` function is the entry point, which sets up the loader parameters and calls `get_data` to yield documents.

1. **Initialize LoaderInterface**: The `loader` function creates an instance of `LoaderInterface` with the specified loader name and parameters.
2. **Get Data**: The `get_data` function attempts to lazily load data using the loader. If lazy loading is not available, it falls back to the regular `load` method.
3. **Yield Documents**: The `loader` function yields documents loaded by the loader.

## Endpoints Used/Created

The `loaders.py` file does not explicitly define or call any endpoints. Its primary focus is on initializing and utilizing document loaders to process data from various sources.