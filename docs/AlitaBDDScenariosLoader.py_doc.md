# AlitaBDDScenariosLoader.py

**Path:** `src/alita_sdk/langchain/document_loaders/AlitaBDDScenariosLoader.py`

## Data Flow

The data flow within the `AlitaBDDScenariosLoader.py` file begins with the initialization of the `BDDScenariosLoader` class, where various parameters related to the Git repository and BDD scenarios are set. The primary data elements include the repository URL, branch, path, and credentials. The data flow proceeds as follows:

1. **Initialization:** The class is initialized with parameters such as `repo_url`, `branch`, `path`, `depth`, `delete_git_dir`, `username`, `password`, `key_filename`, `key_data`, and `path_to_get_features_from`.
2. **Cloning the Repository:** The `__clone_repository` method is called to clone the specified Git repository to the local path.
3. **Parsing BDD Scenarios:** The `__parse_bdd_scenarios` method is invoked to parse the BDD scenarios from the cloned repository. This involves reading the scenarios from the specified directory and converting them into a DataFrame.
4. **Loading Documents:** The `load` method processes the parsed scenarios, creating `Document` objects with the scenario content and metadata. These documents are then returned as a list.
5. **Asynchronous Loading:** The `aload` method provides an asynchronous generator that yields `Document` objects one by one.

Example:
```python
class BDDScenariosLoader(BaseLoader):
    def __init__(self, **kwargs):
        self.repo_url = kwargs.get('source')
        self.branch = kwargs.get('branch', 'main')
        self.path = kwargs.get('path', TemporaryDirectory().name)
        # Additional initialization parameters...

    def __clone_repository(self):
        git.clone(
            source=self.repo_url,
            target=self.path,
            branch=self.branch,
            depth=self.depth,
            delete_git_dir=self.delete_git_dir,
            username=self.username,
            password=self.password,
            key_filename=self.key_filename,
            key_data=self.key_data,
        )

    def __parse_bdd_scenarios(self) -> list[dict]:
        path_to_scenarios = os.path.join(self.path, self.path_to_get_features_from)
        scenarios = get_all_scenarios_from_directory(path_to_scenarios)
        scenarios_data_frame = create_scenarios_data_frame(scenarios)
        scenarios_data_frame.fillna('None', inplace=True)
        data = scenarios_data_frame[['Scenario Name', 'Scenario', 'Test Data', 'Tags']].to_dict('records')
        return data

    def load(self) -> List[Document]:
        self.__clone_repository()
        scenarios = self.__parse_bdd_scenarios()
        result = []
        for scenario in scenarios:
            page_content = scenario['Scenario']
            metadata = {
                'table_source': f'Automated scenarios from repo - {self.repo_url}',
                "source": f"{scenario['Scenario Name']}",
                "columns": list(scenario.keys()),
                "og_data": dumps(scenario),
                "tags": scenario['Tags'],
            }
            doc = Document(page_content=page_content, metadata=metadata)
            result.append(doc)
        return result
```

## Functions Descriptions

### `__init__`

The `__init__` method initializes the `BDDScenariosLoader` class with various parameters related to the Git repository and BDD scenarios. It sets attributes such as `repo_url`, `branch`, `path`, `depth`, `delete_git_dir`, `username`, `password`, `key_filename`, `key_data`, and `path_to_get_features_from`.

### `__clone_repository`

The `__clone_repository` method clones the specified Git repository to the local path using the provided credentials and options. It utilizes the `git.clone` function to perform the cloning operation.

### `__parse_bdd_scenarios`

The `__parse_bdd_scenarios` method parses the BDD scenarios from the cloned repository. It reads the scenarios from the specified directory, converts them into a DataFrame, and returns a list of dictionaries containing the scenario data.

### `load`

The `load` method processes the parsed scenarios, creating `Document` objects with the scenario content and metadata. It returns a list of these `Document` objects.

### `aload`

The `aload` method provides an asynchronous generator that yields `Document` objects one by one. It follows a similar process to the `load` method but allows for asynchronous loading of documents.

## Dependencies Used and Their Descriptions

### `os.path`

The `os.path` module is used for common pathname manipulations. In this file, it is used to join paths and handle file system paths.

### `json.dumps`

The `json.dumps` function is used to convert Python objects into JSON strings. It is used in this file to serialize scenario data into JSON format for metadata.

### `tempfile.TemporaryDirectory`

The `TemporaryDirectory` class from the `tempfile` module is used to create temporary directories. It is used in this file to create a temporary directory for cloning the Git repository.

### `typing`

The `typing` module provides type hints for Python code. In this file, it is used to specify the types of function parameters and return values.

### `langchain_core.document_loaders.BaseLoader`

The `BaseLoader` class from the `langchain_core.document_loaders` module is the base class for document loaders. The `BDDScenariosLoader` class inherits from this base class.

### `langchain_core.documents.Document`

The `Document` class from the `langchain_core.documents` module represents a document with content and metadata. It is used in this file to create `Document` objects for the parsed BDD scenarios.

### `pandas.DataFrame`

The `DataFrame` class from the `pandas` module is used to represent tabular data. In this file, it is used to store and manipulate the parsed BDD scenarios.

### `git`

The `git` module provides functions for interacting with Git repositories. In this file, it is used to clone the specified Git repository.

### `bdd_parser`

The `bdd_parser` module provides functions for parsing BDD scenarios. In this file, it is used to parse the BDD scenarios from the cloned repository and create a DataFrame.

### `print_log`

The `print_log` function from the `log` module is used to print log messages. In this file, it is used to log the repository URL and path during the cloning process.

## Functional Flow

The functional flow of the `AlitaBDDScenariosLoader.py` file involves the following steps:

1. **Initialization:** The `BDDScenariosLoader` class is initialized with various parameters related to the Git repository and BDD scenarios.
2. **Cloning the Repository:** The `__clone_repository` method is called to clone the specified Git repository to the local path.
3. **Parsing BDD Scenarios:** The `__parse_bdd_scenarios` method is invoked to parse the BDD scenarios from the cloned repository. This involves reading the scenarios from the specified directory and converting them into a DataFrame.
4. **Loading Documents:** The `load` method processes the parsed scenarios, creating `Document` objects with the scenario content and metadata. These documents are then returned as a list.
5. **Asynchronous Loading:** The `aload` method provides an asynchronous generator that yields `Document` objects one by one.

Example:
```python
loader = BDDScenariosLoader(source='https://github.com/example/repo.git', branch='main')
documents = loader.load()
for doc in documents:
    print(doc.page_content)
```

## Endpoints Used/Created

The `AlitaBDDScenariosLoader.py` file does not explicitly define or call any endpoints. It primarily focuses on loading BDD scenarios from a Git repository and converting them into `Document` objects.