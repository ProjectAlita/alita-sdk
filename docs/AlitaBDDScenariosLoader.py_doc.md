# AlitaBDDScenariosLoader.py

**Path:** `src/alita_sdk/langchain/document_loaders/AlitaBDDScenariosLoader.py`

## Data Flow

The data flow within the `AlitaBDDScenariosLoader.py` file revolves around the process of cloning a Git repository, parsing BDD (Behavior-Driven Development) scenarios from the repository, and loading these scenarios into a structured format. The data originates from a Git repository specified by the user. The repository is cloned to a local directory, and the BDD scenarios are extracted from this directory. These scenarios are then transformed into a structured format (a list of dictionaries) and finally loaded into `Document` objects for further use.

For example, the `__parse_bdd_scenarios` method is responsible for parsing the BDD scenarios:

```python
    def __parse_bdd_scenarios(self) -> list[dict]:
        if self.path_to_get_features_from:
            path_to_scenarios = os.path.join(self.path, self.path_to_get_features_from)
        else:
            path_to_scenarios = self.path
        scenarios: Generator[ScenarioTemplate, Any, None] = get_all_scenarios_from_directory(path_to_scenarios)
        scenarios_data_frame: DataFrame = create_scenarios_data_frame(scenarios)
        scenarios_data_frame.fillna('None', inplace=True)
        data = scenarios_data_frame[['Scenario Name', 'Scenario', 'Test Data', 'Tags']].to_dict('records')
        return data
```

In this example, the method retrieves the path to the scenarios, parses them into a DataFrame, fills any missing values, and converts the DataFrame into a list of dictionaries.

## Functions Descriptions

### `__init__`

The `__init__` method initializes the `BDDScenariosLoader` class with various parameters such as the repository URL, branch, path, and authentication details. These parameters are used to configure the cloning and parsing process.

### `__clone_repository`

The `__clone_repository` method clones the specified Git repository to a local directory. It uses the `git.clone` function, passing in parameters such as the repository URL, target path, branch, and authentication details.

### `__parse_bdd_scenarios`

The `__parse_bdd_scenarios` method parses the BDD scenarios from the cloned repository. It retrieves the path to the scenarios, parses them into a DataFrame, fills any missing values, and converts the DataFrame into a list of dictionaries.

### `load`

The `load` method clones the repository, parses the BDD scenarios, and loads them into `Document` objects. It returns a list of `Document` objects, each containing the content and metadata of a scenario.

### `aload`

The `aload` method is an asynchronous version of the `load` method. It clones the repository, parses the BDD scenarios, and yields `Document` objects one by one.

## Dependencies Used and Their Descriptions

### `os.path`

Used for handling and manipulating file paths.

### `json.dumps`

Used for converting Python objects into JSON strings.

### `tempfile.TemporaryDirectory`

Used for creating temporary directories.

### `typing`

Provides type hints for better code readability and type checking.

### `langchain_core.document_loaders.BaseLoader`

The base class for creating custom document loaders.

### `langchain_core.documents.Document`

Represents a document with content and metadata.

### `pandas.DataFrame`

Used for creating and manipulating data frames.

### `git`

A custom module for handling Git operations such as cloning repositories.

### `bdd_parser`

A custom module for parsing BDD scenarios from directories and creating data frames.

### `print_log`

A custom logging function for printing log messages.

## Functional Flow

1. **Initialization**: The `BDDScenariosLoader` class is initialized with various parameters such as the repository URL, branch, path, and authentication details.
2. **Cloning Repository**: The `__clone_repository` method clones the specified Git repository to a local directory.
3. **Parsing Scenarios**: The `__parse_bdd_scenarios` method parses the BDD scenarios from the cloned repository and converts them into a list of dictionaries.
4. **Loading Documents**: The `load` method loads the parsed scenarios into `Document` objects and returns them as a list. The `aload` method does the same but yields the `Document` objects one by one.

## Endpoints Used/Created

This file does not explicitly define or call any endpoints. The primary interaction is with the Git repository specified by the user, which is cloned and parsed to extract BDD scenarios.