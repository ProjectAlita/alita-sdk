# AlitaBDDScenariosLoader.py

**Path:** `src/alita_sdk/langchain/document_loaders/AlitaBDDScenariosLoader.py`

## Data Flow

The data flow within the `AlitaBDDScenariosLoader.py` file revolves around the process of cloning a Git repository, parsing BDD (Behavior-Driven Development) scenarios from the repository, and converting these scenarios into a structured format that can be used by other components of the system. The data flow can be summarized as follows:

1. **Initialization:** The `BDDScenariosLoader` class is initialized with various parameters such as the repository URL, branch, path, and authentication details. These parameters are stored as instance variables.

2. **Cloning the Repository:** The `__clone_repository` method is called to clone the specified Git repository to a local directory. This involves using the `git.clone` function with the provided parameters.

3. **Parsing BDD Scenarios:** The `__parse_bdd_scenarios` method is called to parse the BDD scenarios from the cloned repository. This involves using the `get_all_scenarios_from_directory` function to retrieve all scenarios and the `create_scenarios_data_frame` function to convert the scenarios into a DataFrame.

4. **Data Transformation:** The DataFrame is processed to fill any missing values with 'None' and then converted into a list of dictionaries, each representing a scenario with its name, content, test data, and tags.

5. **Loading Documents:** The `load` method creates `Document` objects for each scenario, with the scenario content as the page content and metadata containing information about the scenario. These `Document` objects are returned as a list.

6. **Asynchronous Loading:** The `aload` method performs the same operations as the `load` method but yields `Document` objects one by one, allowing for asynchronous processing.

### Example:

```python
class BDDScenariosLoader(BaseLoader):
    def __init__(self, **kwargs):
        self.repo_url = kwargs.get('source')
        self.branch = kwargs.get('branch', 'main')
        self.path = kwargs.get('path', TemporaryDirectory().name)
        self.depth = kwargs.get('depth', None)
        self.delete_git_dir = kwargs.get('delete_git_dir', True)
        self.username = kwargs.get('username', None)
        self.password = kwargs.get('password', None)
        self.key_filename = kwargs.get('key_filename', None)
        self.key_data = kwargs.get('key_data', None)
        self.path_to_get_features_from = kwargs.get('index_file_exts', None)

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
        if self.path_to_get_features_from:
            path_to_scenarios = os.path.join(self.path, self.path_to_get_features_from)
        else:
            path_to_scenarios = self.path
        scenarios = get_all_scenarios_from_directory(path_to_scenarios)
        scenarios_data_frame = create_scenarios_data_frame(scenarios)
        scenarios_data_frame.fillna('None', inplace=True)
        data = scenarios_data_frame[['Scenario Name', 'Scenario', 'Test Data', 'Tags']].to_dict('records')
        return data
```

## Functions Descriptions

### `__init__(self, **kwargs)`

The constructor method initializes the `BDDScenariosLoader` class with various parameters. It sets up the instance variables needed for cloning the repository and parsing the BDD scenarios.

- **Parameters:**
  - `source`: The URL of the Git repository to clone.
  - `branch`: The branch of the repository to clone (default is 'main').
  - `path`: The local path to clone the repository to (default is a temporary directory).
  - `depth`: The depth of the Git clone (default is None).
  - `delete_git_dir`: Whether to delete the Git directory after loading (default is True).
  - `username`: The Git username for authentication (default is None).
  - `password`: The Git password for authentication (default is None).
  - `key_filename`: The filename of the Git key for authentication (default is None).
  - `key_data`: The data of the Git key for authentication (default is None).
  - `index_file_exts`: The path to search for BDD scenarios inside the cloned repository (default is None).

### `__clone_repository(self)`

This private method clones the specified Git repository to a local directory using the provided parameters. It uses the `git.clone` function to perform the clone operation.

- **No parameters.**

### `__parse_bdd_scenarios(self) -> list[dict]`

This private method parses the BDD scenarios from the cloned repository. It retrieves all scenarios using the `get_all_scenarios_from_directory` function and converts them into a DataFrame using the `create_scenarios_data_frame` function. The DataFrame is then processed to fill missing values and converted into a list of dictionaries.

- **Returns:** A list of dictionaries, each representing a BDD scenario.

### `load(self) -> List[Document]`

This method clones the repository, parses the BDD scenarios, and creates `Document` objects for each scenario. The `Document` objects contain the scenario content and metadata.

- **Returns:** A list of `Document` objects.

### `aload(self) -> Iterator[Document]`

This asynchronous method performs the same operations as the `load` method but yields `Document` objects one by one, allowing for asynchronous processing.

- **Returns:** An iterator of `Document` objects.

## Dependencies Used and Their Descriptions

### `os.path`

Used for handling and manipulating file paths.

### `json.dumps`

Used for converting Python objects into JSON strings.

### `tempfile.TemporaryDirectory`

Used for creating temporary directories.

### `typing`

Used for type hinting and annotations.

### `langchain_core.document_loaders.BaseLoader`

The base class for creating custom document loaders.

### `langchain_core.documents.Document`

Represents a document with content and metadata.

### `pandas.DataFrame`

Used for creating and manipulating data frames.

### `git`

Custom module for handling Git operations such as cloning repositories.

### `bdd_parser.get_all_scenarios_from_directory`

Custom function for retrieving all BDD scenarios from a directory.

### `bdd_parser.create_scenarios_data_frame`

Custom function for converting BDD scenarios into a DataFrame.

### `bdd_parser.parser.ScenarioTemplate`

Represents a template for BDD scenarios.

### `log.print_log`

Custom function for logging messages.

## Functional Flow

The functional flow of the `AlitaBDDScenariosLoader.py` file can be summarized as follows:

1. **Initialization:** The `BDDScenariosLoader` class is initialized with various parameters.
2. **Cloning the Repository:** The `__clone_repository` method is called to clone the specified Git repository.
3. **Parsing BDD Scenarios:** The `__parse_bdd_scenarios` method is called to parse the BDD scenarios from the cloned repository.
4. **Loading Documents:** The `load` method creates `Document` objects for each scenario and returns them as a list.
5. **Asynchronous Loading:** The `aload` method performs the same operations as the `load` method but yields `Document` objects one by one.

### Example:

```python
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

## Endpoints Used/Created

The `AlitaBDDScenariosLoader.py` file does not explicitly define or call any endpoints. The primary focus of the file is on cloning a Git repository, parsing BDD scenarios, and converting them into a structured format for further use.