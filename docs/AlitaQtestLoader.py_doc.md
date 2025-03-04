# AlitaQtestLoader.py

**Path:** `src/alita_sdk/langchain/document_loaders/AlitaQtestLoader.py`

## Data Flow

The data flow within the `AlitaQtestLoader.py` file revolves around fetching, parsing, and transforming test case data from a qTest project into a format suitable for further processing or analysis. The data originates from the qTest API, where it is retrieved using various API calls. The data is then parsed and transformed into a structured format, which is eventually returned as a list of `Document` objects.

The process begins with the initialization of the `AlitaQTestApiDataLoader` class, where the necessary parameters such as `project_id`, `no_of_test_cases_per_page`, `qtest_api_token`, and `qtest_api_base_url` are provided. The data flow can be summarized as follows:

1. **Initialization:** The class is initialized with the required parameters.
2. **Fetching Modules:** The `__get_all_modules_for_project` method retrieves all modules for the specified project using the qTest API.
3. **Parsing Modules:** The `_parse_modules` method parses the retrieved modules into a structured format.
4. **Fetching Test Cases:** Depending on whether a DQL query is provided, the `__fetch_qtest_data_from_project` method either fetches test cases using the DQL query or retrieves them page by page.
5. **Parsing Test Cases:** The `__parse_data` and `__transform_test_data_into_dict` methods parse the test case data into a structured format.
6. **Creating Documents:** The `load` and `lazy_load` methods create `Document` objects from the parsed data and return them.

Example:
```python
class AlitaQTestApiDataLoader(BaseLoader):
    def __init__(self,
                 project_id: int,
                 no_of_test_cases_per_page: int,
                 qtest_api_token: str,
                 qtest_api_base_url: str,
                 dql: Optional[str] = None,
                 columns: Optional[List[str]] = None
                 ):
        self.project_id = project_id
        self.no_of_test_cases_per_page = no_of_test_cases_per_page
        self.qtest_api_token = qtest_api_token
        self.qtest_api_base_url = qtest_api_base_url
        self.columns = columns
        self.dql = dql
```

## Functions Descriptions

### `__init__`

The `__init__` method initializes the `AlitaQTestApiDataLoader` class with the necessary parameters. It sets up the project ID, number of test cases per page, qTest API token, base URL, DQL query, and columns to be retrieved.

### `__get_all_modules_for_project`

This method retrieves all modules for the specified project using the qTest API. It calls the `get_sub_modules_of` method of the `ModuleApi` class and handles any exceptions that may occur during the API call.

### `_parse_modules`

The `_parse_modules` method parses the retrieved modules into a structured format. It recursively processes each module and its children, creating a list of dictionaries containing module IDs and names.

### `__parse_data`

This method parses the test case data retrieved from the qTest API. It processes each test case item, extracting relevant information such as ID, module name, status, type, functional area, squad, description, precondition, test step description, and expected result.

### `__build_qtest_client`

The `__build_qtest_client` method sets up the qTest API client with the necessary configuration, including the base URL and API token.

### `__search_tests_by_dql`

This method searches for test cases using a DQL query. It calls the `search_artifact` method of the `SearchApi` class and handles pagination to retrieve all test cases matching the query.

### `__search_tests`

The `__search_tests` method retrieves test cases page by page using the `get_test_cases` method of the `TestCaseApi` class. It handles pagination and returns the retrieved test cases.

### `__fetch_test_cases_from_qtest_as_data_frame`

This method fetches test cases from the qTest project and transforms them into a list of dictionaries. It handles pagination and calls the `__transform_test_data_into_dict` method to process the retrieved test cases.

### `__transform_test_data_into_dict`

The `__transform_test_data_into_dict` method transforms the test case data into a structured format. It processes each test case item, extracting relevant information and creating a dictionary for each test case.

### `__fetch_qtest_data_from_project`

This method fetches test case data from the qTest project. It either uses a DQL query to search for test cases or retrieves them page by page. The retrieved data is then returned as a list of dictionaries.

### `load`

The `load` method creates `Document` objects from the parsed test case data. It processes each row of data, merges the specified columns, and creates a `Document` object with the merged content and metadata.

### `lazy_load`

The `lazy_load` method is similar to the `load` method but returns an iterator of `Document` objects instead of a list. It processes each row of data, merges the specified columns, and yields a `Document` object with the merged content and metadata.

## Dependencies Used and Their Descriptions

### `logging`

The `logging` module is used for logging error messages and other information throughout the code. It helps in debugging and monitoring the execution of the code.

### `string`

The `string` module is used for string manipulation, such as capitalizing the first letter of a string.

### `json.dumps`

The `dumps` function from the `json` module is used to convert Python objects into JSON strings. It is used to serialize the original data into JSON format for storing in the metadata of `Document` objects.

### `Optional`, `List`, `Iterator`

These types from the `typing` module are used for type hinting, indicating that certain parameters or return values can be of specific types.

### `swagger_client`

The `swagger_client` module is used to interact with the qTest API. It provides various classes and methods for making API calls and handling responses.

### `gensim.parsing.preprocessing.strip_tags`

The `strip_tags` function from the `gensim.parsing.preprocessing` module is used to remove HTML tags from strings. It is used to clean up the description and precondition fields of test cases.

### `BaseLoader`

The `BaseLoader` class from the `langchain_community.document_loaders.base` module is the base class for the `AlitaQTestApiDataLoader` class. It provides common functionality for loading documents.

### `Document`

The `Document` class from the `langchain_core.documents` module represents a document with content and metadata. It is used to create and return the final documents from the loader.

### `SearchApi`, `ModuleApi`, `TestCaseApi`, `ApiException`

These classes from the `swagger_client` module are used to interact with the qTest API. They provide methods for searching artifacts, retrieving modules, and fetching test cases. The `ApiException` class is used to handle exceptions that occur during API calls.

## Functional Flow

The functional flow of the `AlitaQtestLoader.py` file involves the following steps:

1. **Initialization:** The `AlitaQTestApiDataLoader` class is initialized with the required parameters.
2. **Fetching Modules:** The `__get_all_modules_for_project` method retrieves all modules for the specified project using the qTest API.
3. **Parsing Modules:** The `_parse_modules` method parses the retrieved modules into a structured format.
4. **Fetching Test Cases:** Depending on whether a DQL query is provided, the `__fetch_qtest_data_from_project` method either fetches test cases using the DQL query or retrieves them page by page.
5. **Parsing Test Cases:** The `__parse_data` and `__transform_test_data_into_dict` methods parse the test case data into a structured format.
6. **Creating Documents:** The `load` and `lazy_load` methods create `Document` objects from the parsed data and return them.

Example:
```python
def load(self) -> List[Document]:
    documents: List[Document] = []
    qtest_data: list = self.__fetch_qtest_data_from_project()
    if self.columns:
        for row in qtest_data:
            page_content = '\n'.join([col + ":\n" + row[col] for col in self.columns])
            meta = {
                'table_source': f'qTest project id - {self.project_id}',
                'source': str(row['Id']),
                'columns': list(row.keys()),
                'og_data': dumps(row),
            }
            documents.append(Document(page_content, metadata=meta))
    else:
        for row in qtest_data:
            page_content = '\n'.join([col + ":\n" + row[col] for col in row.keys()])
            meta = {
                'table_source': f'qTest project id - {self.project_id}',
                'source': str(row['Id']),
                'columns': list(row.keys()),
                'og_data': dumps(row),
            }
            documents.append(Document(page_content, metadata=meta))
    return documents
```

## Endpoints Used/Created

### `get_sub_modules_of`

- **Type:** qTest API call
- **URL:** `/api/v3/projects/{project_id}/modules/{module_id}/submodules`
- **HTTP Method:** GET
- **Purpose:** Retrieves all submodules for a specified project module.
- **Request Format:** The request includes the project ID and module ID as path parameters.
- **Response Format:** The response contains a list of submodules for the specified project module.

### `search_artifact`

- **Type:** qTest API call
- **URL:** `/api/v3/projects/{project_id}/search`
- **HTTP Method:** POST
- **Purpose:** Searches for artifacts (test cases) in a specified project using a DQL query.
- **Request Format:** The request includes the project ID as a path parameter and the DQL query in the request body.
- **Response Format:** The response contains a list of artifacts (test cases) matching the DQL query.

### `get_test_cases`

- **Type:** qTest API call
- **URL:** `/api/v3/projects/{project_id}/test-cases`
- **HTTP Method:** GET
- **Purpose:** Retrieves test cases for a specified project.
- **Request Format:** The request includes the project ID as a path parameter and pagination parameters (page number and page size) as query parameters.
- **Response Format:** The response contains a list of test cases for the specified project.
