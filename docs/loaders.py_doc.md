# loaders.py

**Path:** `src/alita_sdk/langchain/interfaces/loaders.py`

## Data Flow

The data flow within `loaders.py` begins with the importation of various loader classes from the `langchain_community.document_loaders` module and custom loaders from the `document_loaders` directory. The `LoaderInterface` class is central to the data flow, as it initializes the appropriate loader class based on the provided `loader_name`. The data is then processed through methods like `load`, `load_and_split`, and `lazy_load`, which are called on the loader instance. The `get_data` function further facilitates data flow by yielding documents from the loader. Finally, the `loader` function orchestrates the entire process by setting up the loader with the given parameters and invoking `get_data` to yield documents.

Example:
```python
class LoaderInterface:
    def __init__(self, loader_name, **kwargs):
        self.loader = LoaderInterface.get_loader_cls(loader_name)(**kwargs)

    @staticmethod
    def get_loader_cls(loader_name):
        if loader_name in ex_classes:
            loader = ex_classes[loader_name]
        elif loader_name in loaders:
            loader = getattr(
                __import__("langchain_community.document_loaders", fromlist=[loader_name]), loader_name
            )
        else:
            loader = getattr(
                __import__("langchain_community.document_loaders", fromlist=[loader_name]), 'TextLoader'
            )
        return loader
```
This snippet shows the initialization of a loader class based on the `loader_name` and demonstrates the data flow from the loader class to the `LoaderInterface`.

## Functions Descriptions

### LoaderInterface

- **`__init__(self, loader_name, **kwargs)`**: Initializes the loader interface with the specified loader name and parameters.
- **`get_loader_cls(loader_name)`**: A static method that returns the appropriate loader class based on the loader name.
- **`load(self, *args, **kwargs)`**: Calls the `load` method of the loader instance.
- **`load_and_split(self, *args, **kwargs)`**: Calls the `load_and_split` method of the loader instance.
- **`lazy_load(self, *args, **kwargs)`**: Calls the `lazy_load` method of the loader instance.

### get_data

- **`get_data(loader, load_params)`**: Attempts to lazily load data using the loader and parameters. If lazy loading is not implemented, it falls back to the regular load method. Yields documents from the loader.

### loader

- **`loader(loader_name, loader_params, load_params)`**: Sets up the loader with the given parameters and invokes `get_data` to yield documents.

Example:
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
This function demonstrates how data is loaded and yielded from the loader, handling both lazy loading and regular loading.

## Dependencies Used and Their Descriptions

- **`langchain_community.document_loaders`**: This module provides various document loader classes that are dynamically imported based on the loader name.
- **`AlitaQTestApiDataLoader`**: Custom loader for QTest API data.
- **`AlitaCSVLoader`**: Custom loader for CSV files.
- **`AlitaExcelLoader`**: Custom loader for Excel files.
- **`AlitaDirectoryLoader`**: Custom loader for directories.
- **`AlitaGitRepoLoader`**: Custom loader for Git repositories.
- **`AlitaConfluenceLoader`**: Custom loader for Confluence pages.
- **`BDScenariosLoader`**: Custom loader for BDD scenarios.

These dependencies are essential for the functionality of the `LoaderInterface` class, as they provide the specific implementations for loading different types of documents.

## Functional Flow

The functional flow of `loaders.py` starts with the initialization of the `LoaderInterface` class, which determines the appropriate loader class based on the provided `loader_name`. The loader instance is then used to load data through methods like `load`, `load_and_split`, and `lazy_load`. The `get_data` function facilitates the data loading process by yielding documents from the loader. The `loader` function orchestrates the entire process by setting up the loader with the given parameters and invoking `get_data` to yield documents.

Example:
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
This function demonstrates the setup and invocation of the loader, showing how documents are yielded through the `get_data` function.

## Endpoints Used/Created

There are no explicit endpoints used or created in `loaders.py`. The file focuses on loading data from various sources using different loader classes.