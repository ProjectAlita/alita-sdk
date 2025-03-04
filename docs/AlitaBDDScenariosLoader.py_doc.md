# AlitaBDDScenariosLoader.py

**Path:** `src/alita_sdk/langchain/document_loaders/AlitaBDDScenariosLoader.py`

## Data Flow

The data flow within the `AlitaBDDScenariosLoader.py` file revolves around the process of cloning a Git repository, parsing BDD (Behavior-Driven Development) scenarios, and loading them into a structured format. The data journey begins with the initialization of the `BDDScenariosLoader` class, where various parameters such as the repository URL, branch, and path are set. The `__clone_repository` method is then called to clone the specified Git repository to a local directory. Once the repository is cloned, the `__parse_bdd_scenarios` method is invoked to parse the BDD scenarios from the specified directory. This method uses the `get_all_scenarios_from_directory` function to retrieve all scenarios and the `create_scenarios_data_frame` function to convert them into a DataFrame. The DataFrame is then transformed into a list of dictionaries, each representing a scenario. Finally, the `load` method creates `Document` objects for each scenario, which are returned as the output.

Example:
```python
scenarios: Generator[ScenarioTemplate, Any, None] = get_all_scenarios_from_directory(path_to_scenarios)
scenarios_data_frame: DataFrame = create_scenarios_data_frame(scenarios)
scenarios_data_frame.fillna('None', inplace=True)
data = scenarios_data_frame[['Scenario Name', 'Scenario', 'Test Data', 'Tags']].to_dict('records')
```
In this example, the scenarios are retrieved from the directory, converted into a DataFrame, and then transformed into a list of dictionaries.

## Functions Descriptions

### `__init__(self, **kwargs)`
The constructor initializes the `BDDScenariosLoader` class with various parameters such as the repository URL, branch, path, and authentication details. It sets default values for optional parameters.

### `__clone_repository(self)`
This private method clones the specified Git repository to a local directory using the provided parameters. It utilizes the `git.clone` function to perform the cloning operation.

### `__parse_bdd_scenarios(self) -> list[dict]`
This private method parses the BDD scenarios from the specified directory. It retrieves all scenarios using the `get_all_scenarios_from_directory` function and converts them into a DataFrame using the `create_scenarios_data_frame` function. The DataFrame is then transformed into a list of dictionaries, each representing a scenario.

### `load(self) -> List[Document]`
This method clones the repository, parses the BDD scenarios, and creates `Document` objects for each scenario. It returns a list of `Document` objects.

### `aload(self) -> Iterator[Document]`
This asynchronous method performs the same operations as the `load` method but returns an iterator of `Document` objects instead of a list.

## Dependencies Used and Their Descriptions

### `os.path`
Used for handling and manipulating file paths.

### `json.dumps`
Used for converting Python objects into JSON strings.

### `tempfile.TemporaryDirectory`
Used for creating temporary directories.

### `typing`
Provides type hints for function signatures.

### `langchain_core.document_loaders.BaseLoader`
The base class for creating custom document loaders.

### `langchain_core.documents.Document`
Represents a document with content and metadata.

### `pandas.DataFrame`
Used for creating and manipulating DataFrames.

### `git`
Custom module for performing Git operations such as cloning repositories.

### `bdd_parser.get_all_scenarios_from_directory`
Function for retrieving all BDD scenarios from a specified directory.

### `bdd_parser.create_scenarios_data_frame`
Function for converting BDD scenarios into a DataFrame.

### `bdd_parser.parser.ScenarioTemplate`
Represents a template for BDD scenarios.

### `log.print_log`
Custom logging function for printing log messages.

## Functional Flow

1. **Initialization**: The `BDDScenariosLoader` class is initialized with various parameters such as the repository URL, branch, path, and authentication details.
2. **Cloning Repository**: The `__clone_repository` method is called to clone the specified Git repository to a local directory.
3. **Parsing BDD Scenarios**: The `__parse_bdd_scenarios` method is invoked to parse the BDD scenarios from the specified directory. The scenarios are retrieved, converted into a DataFrame, and transformed into a list of dictionaries.
4. **Loading Documents**: The `load` method creates `Document` objects for each scenario and returns them as a list. The `aload` method performs the same operations but returns an iterator of `Document` objects.

## Endpoints Used/Created

No explicit endpoints are defined or called within the `AlitaBDDScenariosLoader.py` file. The functionality primarily revolves around Git operations and file parsing.