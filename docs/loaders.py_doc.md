# loaders.py

**Path:** `src/alita_sdk/langchain/interfaces/loaders.py`

## Data Flow

The data flow within `loaders.py` revolves around the dynamic loading and processing of documents using various loader classes. The primary data elements are the document loaders, which are instantiated based on the provided loader name. The data flow can be summarized as follows:

1. **Loader Initialization:** The `LoaderInterface` class is initialized with a loader name and optional parameters. This class dynamically determines the appropriate loader class from either the `ex_classes` dictionary or the `langchain_community.document_loaders` module.
2. **Data Loading:** The `load`, `load_and_split`, and `lazy_load` methods of the loader class are called to load the documents. These methods handle the actual data retrieval and processing.
3. **Data Yielding:** The `get_data` function yields the loaded documents one by one, allowing for efficient data processing.

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

### `LoaderInterface.__init__`

**Purpose:** Initializes the `LoaderInterface` with the specified loader name and parameters.

**Inputs:**
- `loader_name`: The name of the loader to be used.
- `kwargs`: Additional parameters for the loader.

**Processing Logic:**
- Calls the `get_loader_cls` method to retrieve the appropriate loader class.
- Instantiates the loader class with the provided parameters.

**Outputs:** None.

### `LoaderInterface.get_loader_cls`

**Purpose:** Retrieves the loader class based on the provided loader name.

**Inputs:**
- `loader_name`: The name of the loader to be retrieved.

**Processing Logic:**
- Checks if the loader name exists in the `ex_classes` dictionary.
- If not, checks if the loader name exists in the `langchain_community.document_loaders` module.
- If not, defaults to the `TextLoader` class.

**Outputs:** The loader class.

### `LoaderInterface.load`

**Purpose:** Loads the documents using the loader's `load` method.

**Inputs:**
- `args`: Positional arguments for the loader's `load` method.
- `kwargs`: Keyword arguments for the loader's `load` method.

**Processing Logic:** Calls the loader's `load` method with the provided arguments.

**Outputs:** The loaded documents.

### `LoaderInterface.load_and_split`

**Purpose:** Loads and splits the documents using the loader's `load_and_split` method.

**Inputs:**
- `args`: Positional arguments for the loader's `load_and_split` method.
- `kwargs`: Keyword arguments for the loader's `load_and_split` method.

**Processing Logic:** Calls the loader's `load_and_split` method with the provided arguments.

**Outputs:** The loaded and split documents.

### `LoaderInterface.lazy_load`

**Purpose:** Lazily loads the documents using the loader's `lazy_load` method.

**Inputs:**
- `args`: Positional arguments for the loader's `lazy_load` method.
- `kwargs`: Keyword arguments for the loader's `lazy_load` method.

**Processing Logic:** Calls the loader's `lazy_load` method with the provided arguments.

**Outputs:** The lazily loaded documents.

### `get_data`

**Purpose:** Yields the loaded documents one by one.

**Inputs:**
- `loader`: The loader instance.
- `load_params`: Parameters for the loader's `load` or `lazy_load` method.

**Processing Logic:**
- Tries to call the loader's `lazy_load` method.
- If `lazy_load` is not implemented, calls the loader's `load` method.
- Yields the loaded documents one by one.

**Outputs:** The loaded documents.

### `loader`

**Purpose:** Initializes the loader and yields the loaded documents.

**Inputs:**
- `loader_name`: The name of the loader to be used.
- `loader_params`: Parameters for the loader initialization.
- `load_params`: Parameters for the loader's `load` or `lazy_load` method.

**Processing Logic:**
- Initializes the `LoaderInterface` with the provided loader name and parameters.
- Calls the `get_data` function to yield the loaded documents.

**Outputs:** The loaded documents.

## Dependencies Used and Their Descriptions

### `langchain_community.document_loaders`

**Purpose:** Provides various document loader classes used for loading and processing documents.

**Usage in the File:**
- The `loaders` variable imports all available loader classes from this module.
- The `get_loader_cls` method dynamically imports loader classes from this module if they are not found in the `ex_classes` dictionary.

### `AlitaQTestApiDataLoader`, `AlitaCSVLoader`, `AlitaExcelLoader`, `AlitaDirectoryLoader`, `AlitaGitRepoLoader`, `AlitaConfluenceLoader`, `BDDScenariosLoader`

**Purpose:** Custom loader classes for specific data sources.

**Usage in the File:**
- These classes are imported and stored in the `ex_classes` dictionary for quick access.

## Functional Flow

1. **Initialization:** The `LoaderInterface` class is initialized with a loader name and parameters.
2. **Loader Class Retrieval:** The `get_loader_cls` method retrieves the appropriate loader class based on the loader name.
3. **Data Loading:** The `load`, `load_and_split`, or `lazy_load` method of the loader class is called to load the documents.
4. **Data Yielding:** The `get_data` function yields the loaded documents one by one.
5. **Loader Function:** The `loader` function initializes the `LoaderInterface` and yields the loaded documents using the `get_data` function.

## Endpoints Used/Created

No explicit endpoints are defined or used within this file. The file focuses on dynamically loading and processing documents using various loader classes.