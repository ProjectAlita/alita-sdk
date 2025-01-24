# AlitaQtestLoader.py

**Path:** `src/alita_sdk/langchain/document_loaders/AlitaQtestLoader.py`

## Data Flow

The data flow within the `AlitaQTestApiDataLoader` class is structured to interact with the qTest API, retrieve test case data, and transform it into a format suitable for further processing or analysis. The journey of data begins with the initialization of the loader, where essential parameters such as `project_id`, `no_of_test_cases_per_page`, `qtest_api_token`, and `qtest_api_base_url` are set. These parameters are used to configure the API client and define the scope of data retrieval.

The data retrieval process involves multiple steps:
1. **Module Retrieval:** The `__get_all_modules_for_project` method fetches all modules for the specified project using the qTest API. This data is parsed and stored in a list of dictionaries, each representing a module with its ID and name.
2. **Test Case Retrieval:** Depending on whether a DQL (qTest's query language) is provided, the loader either searches for test cases using the DQL (`__search_tests_by_dql`) or fetches test cases page by page (`__fetch_test_cases_from_qtest_as_data_frame`). The retrieved data includes test case details and associated test steps.
3. **Data Parsing:** The `__parse_data` method processes the raw API response, extracting relevant fields and transforming them into a structured format. This includes unescaping HTML content, stripping tags, and organizing test steps and expected results.
4. **Document Creation:** The `load` and `lazy_load` methods convert the parsed data into `Document` objects, which are then returned for further use. These methods also handle the inclusion of specified columns and metadata.

Example:
```python
# Example of data parsing in __parse_data method
for item in response_to_parse['items']:
    if item.get('test_steps', []):
        parsed_data_row = {
            'Id': item['pid'],
            'Module': ''.join([mod['module_name'] for mod in parsed_modules if mod['module_id'] == item['parent_id']]),
            'Name': item['name'],
            'Status': ''.join([properties['field_value_name'] for properties in item['properties']
                               if properties['field_name'] == 'Status']),
            'Type': ''.join([properties['field_value_name'] for properties in item['properties']
                               if properties['field_name'] == 'Type']),
            'Functional Area': ''.join([properties['field_value_name'] for properties in item['properties']
                               if properties['field_name'] == 'Functional Area']),
            'Squad': ''.join([properties['field_value_name'] for properties in item['properties']
                               if properties['field_name'] == 'Squad']),
            'Description': html.unescape(strip_tags(item['description'])),
            'Precondition': html.unescape(strip_tags(item['precondition'])),
            'Test Step Description': '\n'.join(map(str,
                                                   [html.unescape(
                                                       strip_tags(str(item['order']) + '. ' + item['description']))
                                                       for item in item['test_steps']
                                                       for key in item if key == 'description'])),
            'Test Expected Result': '\n'.join(map(str,
                                                  [html.unescape(
                                                      strip_tags(str(item['order']) + '. ' + item['expected']))
                                                      for item in item['test_steps']
                                                      for key in item if key == 'expected'])),
        }
        parsed_data.append(parsed_data_row)
```

## Functions Descriptions

### `__init__`
The constructor initializes the `AlitaQTestApiDataLoader` with the necessary parameters for interacting with the qTest API. It sets up the project ID, number of test cases per page, API token, base URL, optional DQL, and columns to be retrieved.

### `__get_all_modules_for_project`
This private method retrieves all modules for the specified project using the qTest API. It handles API exceptions and logs errors if the retrieval fails. The method returns a list of modules, each containing its ID and name.

### `_parse_modules`
This method parses the retrieved modules into a list of dictionaries, each representing a module with its ID and name. It recursively processes child modules to build a complete module hierarchy.

### `__parse_data`
This private method processes the raw API response, extracting relevant fields and transforming them into a structured format. It handles HTML unescaping, tag stripping, and organizes test steps and expected results into a readable format.

### `__build_qtest_client`
This private method configures and returns a qTest API client using the provided API token and base URL. It sets up the necessary authentication headers for API requests.

### `__search_tests_by_dql`
This private method searches for test cases using the provided DQL. It handles pagination and processes the API response to extract test case details and associated test steps. The method returns a list of parsed test cases.

### `__search_tests`
This private method retrieves test cases page by page using the qTest API. It handles API exceptions and logs errors if the retrieval fails. The method returns the raw API response for further processing.

### `__fetch_test_cases_from_qtest_as_data_frame`
This private method fetches test cases from the qTest API and transforms them into a list of dictionaries. It handles pagination and processes the API response to extract test case details and associated test steps.

### `__transform_test_data_into_dict`
This static method transforms the raw API response into a list of dictionaries, each representing a test case with its details and associated test steps. It handles HTML unescaping, tag stripping, and organizes test steps and expected results into a readable format.

### `__fetch_qtest_data_from_project`
This private method fetches test case data from the qTest project, either using the provided DQL or by retrieving test cases page by page. It returns a list of parsed test cases.

### `load`
This method loads the test case data and converts it into a list of `Document` objects. It handles the inclusion of specified columns and metadata, and returns the list of documents for further use.

### `lazy_load`
This method lazily loads the test case data and yields `Document` objects one by one. It handles the inclusion of specified columns and metadata, and returns an iterator for further use.

## Dependencies Used and Their Descriptions

### `logging`
Used for logging error messages and debugging information.

### `string`
Provides string manipulation functions, such as `capwords` for capitalizing words.

### `json.dumps`
Used for converting Python objects into JSON strings.

### `Optional`, `List`, `Iterator`
Type hints from the `typing` module for specifying optional parameters, lists, and iterators.

### `swagger_client`
The client library for interacting with the qTest API. It includes various API classes such as `ModuleApi`, `SearchApi`, and `TestCaseApi` for retrieving modules, searching for test cases, and fetching test case details.

### `gensim.parsing.preprocessing.strip_tags`
Used for stripping HTML tags from strings.

### `langchain_community.document_loaders.base.BaseLoader`
The base class for document loaders in the Langchain community library.

### `langchain_core.documents.Document`
The `Document` class from the Langchain core library, used for representing documents with content and metadata.

### `swagger_client.rest.ApiException`
Exception class for handling API errors from the qTest client library.

## Functional Flow

The functional flow of the `AlitaQTestApiDataLoader` class involves the following steps:
1. **Initialization:** The loader is initialized with the necessary parameters for interacting with the qTest API.
2. **Module Retrieval:** The `__get_all_modules_for_project` method fetches all modules for the specified project.
3. **Test Case Retrieval:** Depending on whether a DQL is provided, the loader either searches for test cases using the DQL or fetches test cases page by page.
4. **Data Parsing:** The `__parse_data` method processes the raw API response, extracting relevant fields and transforming them into a structured format.
5. **Document Creation:** The `load` and `lazy_load` methods convert the parsed data into `Document` objects, which are then returned for further use.

Example:
```python
# Example of functional flow in load method
def load(self) -> List[Document]:
    documents: List[Document] = []
    qtest_data: list = self.__fetch_qtest_data_from_project()
    if self.columns:
        for row in qtest_data:
            # Merge specified content using a new line symbol
            page_content = '\n'.join([col + ":\n" + row[col] for col in self.columns])
            # Create metadata dictionary
            meta = {
                'table_source': f'qTest project id - {self.project_id}',
                'source': str(row['Id']),
                'columns': list(row.keys()),
                'og_data': dumps(row),
            }
            # Create Langchain document and add to the list
            documents.append(Document(page_content, metadata=meta))
    else:
        for row in qtest_data:
            # Merge specified content using a new line symbol
            page_content = '\n'.join([col + ":\n" + row[col] for col in row.keys()])
            # Create metadata dictionary
            meta = {
                'table_source': f'qTest project id - {self.project_id}',
                'source': str(row['Id']),
                'columns': list(row.keys()),
                'og_data': dumps(row),
            }
            # Create Langchain document and add to the list
            documents.append(Document(page_content, metadata=meta))
    return documents
```

## Endpoints Used/Created

### `ModuleApi.get_sub_modules_of`
- **Type:** qTest API call
- **URL:** Derived from `qtest_api_base_url`
- **HTTP Method:** GET
- **Purpose:** Retrieves all sub-modules for the specified project.
- **Request Format:** Project ID and expand parameter.
- **Response Format:** List of modules with their details.

### `SearchApi.search_artifact`
- **Type:** qTest API call
- **URL:** Derived from `qtest_api_base_url`
- **HTTP Method:** POST
- **Purpose:** Searches for test cases using the provided DQL.
- **Request Format:** Project ID, search parameters, and pagination details.
- **Response Format:** List of test cases with their details.

### `TestCaseApi.get_test_cases`
- **Type:** qTest API call
- **URL:** Derived from `qtest_api_base_url`
- **HTTP Method:** GET
- **Purpose:** Retrieves test cases page by page for the specified project.
- **Request Format:** Project ID, pagination details, and expand steps parameter.
- **Response Format:** List of test cases with their details.
