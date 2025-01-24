# AlitaQtestLoader.py

**Path:** `src/alita_sdk/langchain/document_loaders/AlitaQtestLoader.py`

## Data Flow

The data flow within `AlitaQtestLoader.py` revolves around fetching and processing test case data from a qTest project. The data originates from the qTest API, where it is retrieved using various API endpoints. The data is then parsed and transformed into a structured format suitable for further processing or storage.

The primary data elements include test case details such as ID, name, status, type, functional area, squad, description, precondition, test steps, and expected results. These elements are initially fetched as raw JSON responses from the qTest API and are subsequently parsed and cleaned to remove HTML tags and escape sequences.

The data flow can be summarized as follows:
1. **Initialization:** The `AlitaQTestApiDataLoader` class is initialized with project-specific parameters such as project ID, API token, base URL, and optional DQL query and columns.
2. **Module Retrieval:** The `__get_all_modules_for_project` method fetches all modules for the specified project, which are then parsed by the `_parse_modules` method.
3. **Data Fetching:** Depending on whether a DQL query is provided, the `__fetch_qtest_data_from_project` method either calls `__search_tests_by_dql` or `__fetch_test_cases_from_qtest_as_data_frame` to retrieve test case data.
4. **Data Parsing:** The `__parse_data` and `__transform_test_data_into_dict` methods parse the raw JSON responses, extracting relevant fields and cleaning the data.
5. **Document Creation:** The `load` and `lazy_load` methods create `Document` objects from the parsed data, which can then be used for further processing.

Example:
```python
# Example of data transformation in __transform_test_data_into_dict
for obj in json_response:
    if not obj.get('test_steps'):
        continue
    api_data_dict = {}
    for key, value in obj.items():
        if key not in fields_to_pick:
            continue
        if key == 'test_steps':
            descriptions = []
            expected_results = []
            for step in value:
                order = str(step.get('order', ''))
                description = html.unescape(strip_tags(step.get('description', '')))
                expected = html.unescape(strip_tags(step.get('expected', '')))
                descriptions.append(f"{order}. {description}")
                expected_results.append(f"{order}. {expected}")
            api_data_dict['Test Step Description'] = '\n'.join(descriptions)
            api_data_dict['Test Expected Result'] = '\n'.join(expected_results)
        elif key in ['description', 'precondition']:
            filtered_data = html.unescape(strip_tags(value))
            api_data_dict[string.capwords(key)] = filtered_data
        elif key == 'pid':
            api_data_dict['Id'] = value
        else:
            api_data_dict[string.capwords(key)] = value
    result.append(api_data_dict)
```

## Functions Descriptions

### `__init__`
The constructor initializes the `AlitaQTestApiDataLoader` class with the necessary parameters such as project ID, number of test cases per page, API token, base URL, optional DQL query, and columns. These parameters are stored as instance variables for use in other methods.

### `__get_all_modules_for_project`
This method retrieves all modules for the specified project using the qTest API. It calls the `get_sub_modules_of` method from the `ModuleApi` class and handles any exceptions that may occur. The retrieved modules are returned as a list.

### `_parse_modules`
This method parses the modules retrieved by `__get_all_modules_for_project` into a list of dictionaries containing module IDs and names. It uses a recursive helper function to parse child modules if they exist.

### `__parse_data`
This method parses the raw JSON response from the qTest API, extracting relevant fields and cleaning the data. It processes each test case item, extracting fields such as ID, module name, name, status, type, functional area, squad, description, precondition, test step descriptions, and expected results.

### `__build_qtest_client`
This method builds and returns a qTest API client using the provided API token and base URL. It configures the client with the necessary authentication headers.

### `__search_tests_by_dql`
This method searches for test cases using a DQL query. It calls the `search_artifact` method from the `SearchApi` class and handles pagination to retrieve all test cases. The retrieved data is parsed using the `__parse_data` method.

### `__search_tests`
This method retrieves test cases for a specific page number using the `get_test_cases` method from the `TestCaseApi` class. It handles any exceptions that may occur and returns the API response.

### `__fetch_test_cases_from_qtest_as_data_frame`
This method fetches test cases from the qTest project, handling pagination to retrieve all test cases. It calls the `__search_tests` method for each page and transforms the retrieved data into a list of dictionaries using the `__transform_test_data_into_dict` method.

### `__transform_test_data_into_dict`
This static method transforms the raw JSON response into a list of dictionaries, extracting relevant fields and cleaning the data. It processes each test case item, extracting fields such as name, ID, description, precondition, test step descriptions, and expected results.

### `__fetch_qtest_data_from_project`
This method fetches test case data from the qTest project, either using a DQL query or by retrieving all test cases. It calls the appropriate method based on whether a DQL query is provided and returns the retrieved data.

### `load`
This method loads the test case data and creates a list of `Document` objects from the parsed data. It merges the specified columns into the document content and adds metadata such as the project ID, source ID, columns, and original data.

### `lazy_load`
This method lazily loads the test case data, yielding `Document` objects one by one. It merges the specified columns into the document content and adds metadata such as the project ID, source ID, columns, and original data.

## Dependencies Used and Their Descriptions

### `logging`
Used for logging error messages and other information.

### `string`
Used for string manipulation, such as capitalizing keys in dictionaries.

### `json.dumps`
Used for converting dictionaries to JSON strings for storing original data in metadata.

### `Optional`, `List`, `Iterator`
Used for type hinting and annotations.

### `swagger_client`
Used for interacting with the qTest API. It provides classes and methods for making API calls and handling responses.

### `gensim.parsing.preprocessing.strip_tags`
Used for removing HTML tags from strings.

### `langchain_community.document_loaders.base.BaseLoader`
Base class for document loaders in the Langchain community.

### `langchain_core.documents.Document`
Class for creating document objects with content and metadata.

### `swagger_client.SearchApi`, `swagger_client.rest.ApiException`
Used for searching test cases using DQL queries and handling API exceptions.

## Functional Flow

The functional flow of `AlitaQtestLoader.py` involves the following steps:
1. **Initialization:** The `AlitaQTestApiDataLoader` class is initialized with project-specific parameters.
2. **Module Retrieval:** The `__get_all_modules_for_project` method fetches all modules for the specified project.
3. **Data Fetching:** The `__fetch_qtest_data_from_project` method retrieves test case data using either a DQL query or by fetching all test cases.
4. **Data Parsing:** The `__parse_data` and `__transform_test_data_into_dict` methods parse and clean the raw JSON responses.
5. **Document Creation:** The `load` and `lazy_load` methods create `Document` objects from the parsed data, which can then be used for further processing.

Example:
```python
# Example of fetching and parsing test case data
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
```

## Endpoints Used/Created

### `ModuleApi.get_sub_modules_of`
**Type:** qTest API call
**URL:** `/api/v3/projects/{project_id}/modules/{module_id}/submodules`
**Method:** GET
**Purpose:** Retrieves all submodules for a specified project module.

### `SearchApi.search_artifact`
**Type:** qTest API call
**URL:** `/api/v3/projects/{project_id}/search`
**Method:** POST
**Purpose:** Searches for test cases using a DQL query.

### `TestCaseApi.get_test_cases`
**Type:** qTest API call
**URL:** `/api/v3/projects/{project_id}/test-cases`
**Method:** GET
**Purpose:** Retrieves test cases for a specified project.
