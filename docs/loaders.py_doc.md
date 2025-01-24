# loaders.py

**Path:** `src/alita_sdk/langchain/interfaces/loaders.py`

## Data Flow

The data flow within `loaders.py` revolves around the creation and utilization of various document loaders. The primary data elements are the loader classes and the documents they process. The data flow can be summarized as follows:

1. **Loader Class Initialization:** The `LoaderInterface` class is initialized with a specific loader name and parameters. This involves selecting the appropriate loader class from the `ex_classes` dictionary or dynamically importing it from the `langchain_community.document_loaders` module.

2. **Data Loading:** The `load`, `load_and_split`, and `lazy_load` methods of the loader class are called to process documents. These methods handle the actual data loading, splitting, and lazy loading of documents.

3. **Data Retrieval:** The `get_data` function retrieves data from the loader by calling its `lazy_load` or `load` method. This function yields the loaded documents one by one.

4. **Loader Function:** The `loader` function orchestrates the entire process by initializing the `LoaderInterface`, calling the `get_data` function, and yielding the documents.

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

## Functions Descriptions

### LoaderInterface

- **`__init__(self, loader_name, **kwargs)`**: Initializes the `LoaderInterface` with a specific loader name and parameters. It selects the appropriate loader class and creates an instance of it.
- **`get_loader_cls(loader_name)`**: A static method that retrieves the loader class based on the loader name. It first checks the `ex_classes` dictionary, then dynamically imports the loader class from the `langchain_community.document_loaders` module.
- **`load(self, *args, **kwargs)`**: Calls the `load` method of the loader instance to load documents.
- **`load_and_split(self, *args, **kwargs)`**: Calls the `load_and_split` method of the loader instance to load and split documents.
- **`lazy_load(self, *args, **kwargs)`**: Calls the `lazy_load` method of the loader instance to lazily load documents.

### get_data

- **`get_data(loader, load_params)`**: Retrieves data from the loader by calling its `lazy_load` or `load` method. It yields the loaded documents one by one.

### loader

- **`loader(loader_name, loader_params, load_params)`**: Orchestrates the entire loading process. It initializes the `LoaderInterface`, calls the `get_data` function, and yields the documents.

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

## Dependencies Used and Their Descriptions

### langchain_community.document_loaders

- **Purpose:** This module provides various document loader classes that are used to load and process different types of documents.
- **Usage:** The `loaders.py` file imports all available loaders from this module and dynamically imports specific loader classes based on the loader name.

### AlitaQTestApiDataLoader, AlitaCSVLoader, AlitaExcelLoader, AlitaDirectoryLoader, AlitaGitRepoLoader, AlitaConfluenceLoader, BDDScenariosLoader

- **Purpose:** These are custom loader classes defined in the `document_loaders` module. They handle loading documents from various sources such as QTest API, CSV files, Excel files, directories, Git repositories, Confluence, and BDD scenarios.
- **Usage:** These classes are included in the `ex_classes` dictionary and are used by the `LoaderInterface` class to load documents.

Example:
```python
from ..document_loaders.AlitaQtestLoader import AlitaQTestApiDataLoader
from ..document_loaders.AlitaCSVLoader import AlitaCSVLoader
from ..document_loaders.AlitaExcelLoader import AlitaExcelLoader
from ..document_loaders.AlitaDirectoryLoader import AlitaDirectoryLoader
from ..document_loaders.AlitaGitRepoLoader import AlitaGitRepoLoader
from ..document_loaders.AlitaConfluenceLoader import AlitaConfluenceLoader
from ..document_loaders.AlitaBDDScenariosLoader import BDDScenariosLoader
```

## Functional Flow

1. **Initialization:** The `LoaderInterface` class is initialized with a loader name and parameters. It selects the appropriate loader class and creates an instance of it.
2. **Data Loading:** The `load`, `load_and_split`, or `lazy_load` method of the loader instance is called to load documents.
3. **Data Retrieval:** The `get_data` function retrieves data from the loader by calling its `lazy_load` or `load` method. It yields the loaded documents one by one.
4. **Loader Function:** The `loader` function orchestrates the entire process by initializing the `LoaderInterface`, calling the `get_data` function, and yielding the documents.

Example:
```python
def loader(loader_name, loader_params, load_params):
    loader_params = loader_params.copy()
    #
    if loader_name == "ExcelLoader":
        loader_params.pop("autodetect_encoding", None)
        loader_params.pop("encoding", None)
    #
    if loader_params.get('loader_cls'):
        loader_cls = LoaderInterface.get_loader_cls(loader_params.get('loader_cls'))
        loader_params['loader_cls'] = loader_cls
    #
    loader = LoaderInterface(loader_name, **loader_params)
    for document in get_data(loader, load_params):
        yield document
```

## Endpoints Used/Created

The `loaders.py` file does not explicitly define or call any endpoints. Its primary focus is on loading and processing documents using various loader classes.