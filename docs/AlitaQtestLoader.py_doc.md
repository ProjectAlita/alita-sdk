# AlitaQtestLoader.py

**Path:** `src/alita_sdk/langchain/document_loaders/AlitaQtestLoader.py`

## Data Flow

The data flow within the `AlitaQtestLoader.py` file revolves around fetching and processing test case data from a qTest project. The data originates from the qTest API, where it is retrieved using various API calls. The data is then parsed and transformed into a structured format suitable for further processing or storage. The main steps in the data flow are as follows:

1. **Initialization:** The `AlitaQTestApiDataLoader` class is initialized with parameters such as `project_id`, `no_of_test_cases_per_page`, `qtest_api_token`, `qtest_api_base_url`, `dql`, and `columns`.
2. **Fetching Modules:** The `__get_all_modules_for_project` method retrieves all modules for the specified project using the qTest API.
3. **Parsing Modules:** The `_parse_modules` method parses the retrieved modules into a list of dictionaries containing module IDs and names.
4. **Fetching Test Cases:** Depending on whether a DQL (qTest query language) is provided, test cases are fetched using either the `__search_tests_by_dql` method or the `__fetch_test_cases_from_qtest_as_data_frame` method.
5. **Parsing Test Cases:** The `__parse_data` and `__transform_test_data_into_dict` methods parse the fetched test cases into a structured format.
6. **Loading Documents:** The `load` and `lazy_load` methods convert the parsed test case data into `Document` objects, which are then returned or yielded.

Example:
```python
# Fetching modules for the project
modules = self.__get_all_modules_for_project()

# Parsing modules
parsed_modules = self._parse_modules()

# Fetching test cases using DQL
qtest_data = self.__search_tests_by_dql()

# Parsing test cases
self.__parse_data(api_response, parsed_data, parsed_modules)
```

## Functions Descriptions

### `__init__`

The `__init__` method initializes the `AlitaQTestApiDataLoader` class with the necessary parameters. It sets up the project ID, number of test cases per page, qTest API token, qTest API base URL, DQL, and columns.

### `__get_all_modules_for_project`

This method retrieves all modules for the specified project using the qTest API. It calls the `get_sub_modules_of` method of the `ModuleApi` class and handles any exceptions that may occur.

### `_parse_modules`

The `_parse_modules` method parses the retrieved modules into a list of dictionaries containing module IDs and names. It recursively parses child modules if they exist.

### `__parse_data`

This method parses the fetched test case data into a structured format. It extracts relevant information such as test steps, descriptions, and expected results, and stores them in a list of dictionaries.

### `__build_qtest_client`

The `__build_qtest_client` method sets up the qTest API client with the necessary configuration, including the API token and base URL.

### `__search_tests_by_dql`

This method searches for test cases using the provided DQL. It calls the `search_artifact` method of the `SearchApi` class and handles pagination to retrieve all test cases.

### `__search_tests`

The `__search_tests` method retrieves test cases for the specified project and page number using the `get_test_cases` method of the `TestCaseApi` class.

### `__fetch_test_cases_from_qtest_as_data_frame`

This method fetches test cases from the qTest project and transforms them into a list of dictionaries. It handles pagination and calls the `__transform_test_data_into_dict` method to parse the test case data.

### `__transform_test_data_into_dict`

This method transforms the fetched test case data into a list of dictionaries. It extracts relevant fields such as name, description, precondition, and test steps, and formats them appropriately.

### `__fetch_qtest_data_from_project`

This method fetches test case data from the qTest project using either the DQL or the default method. It returns the parsed test case data as a list of dictionaries.

### `load`

The `load` method converts the parsed test case data into `Document` objects and returns them as a list. It merges specified columns into the document content and adds metadata.

### `lazy_load`

The `lazy_load` method is similar to the `load` method but yields `Document` objects one by one instead of returning a list. This allows for lazy loading of documents.

## Dependencies Used and Their Descriptions

### `logging`

The `logging` module is used for logging error messages and other information throughout the code.

### `string`

The `string` module is used for string manipulation, such as capitalizing field names.

### `json.dumps`

The `dumps` function from the `json` module is used to convert dictionaries to JSON strings for storing metadata.

### `Optional`, `List`, `Iterator`

These types from the `typing` module are used for type hinting and specifying optional parameters, lists, and iterators.

### `swagger_client`

The `swagger_client` module is used to interact with the qTest API. It provides classes such as `ModuleApi`, `SearchApi`, and `TestCaseApi` for making API calls.

### `gensim.parsing.preprocessing.strip_tags`

The `strip_tags` function from the `gensim.parsing.preprocessing` module is used to remove HTML tags from strings.

### `BaseLoader`

The `BaseLoader` class from the `langchain_community.document_loaders.base` module is the base class for the `AlitaQTestApiDataLoader` class.

### `Document`

The `Document` class from the `langchain_core.documents` module is used to create document objects that store the parsed test case data.

### `ApiException`

The `ApiException` class from the `swagger_client.rest` module is used to handle exceptions that occur during API calls.

## Functional Flow

The functional flow of the `AlitaQtestLoader.py` file involves the following steps:

1. **Initialization:** The `AlitaQTestApiDataLoader` class is initialized with the necessary parameters.
2. **Fetching Modules:** The `__get_all_modules_for_project` method retrieves all modules for the specified project.
3. **Parsing Modules:** The `_parse_modules` method parses the retrieved modules into a list of dictionaries.
4. **Fetching Test Cases:** The `__fetch_qtest_data_from_project` method fetches test cases using either the DQL or the default method.
5. **Parsing Test Cases:** The `__parse_data` and `__transform_test_data_into_dict` methods parse the fetched test cases into a structured format.
6. **Loading Documents:** The `load` and `lazy_load` methods convert the parsed test case data into `Document` objects and return or yield them.

Example:
```python
# Initialize the data loader
loader = AlitaQTestApiDataLoader(project_id=123, no_of_test_cases_per_page=10, qtest_api_token='token', qtest_api_base_url='https://api.qtest.com')

# Load documents
documents = loader.load()
```

## Endpoints Used/Created

### `get_sub_modules_of`

- **Type:** qTest API
- **URL:** `/api/v3/projects/{project_id}/modules/{module_id}/submodules`
- **Method:** GET
- **Description:** Retrieves submodules for the specified project and module.

### `search_artifact`

- **Type:** qTest API
- **URL:** `/api/v3/projects/{project_id}/search`
- **Method:** POST
- **Description:** Searches for artifacts (test cases) in the specified project using DQL.

### `get_test_cases`

- **Type:** qTest API
- **URL:** `/api/v3/projects/{project_id}/test-cases`
- **Method:** GET
- **Description:** Retrieves test cases for the specified project.
