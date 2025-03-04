# jira_issues.py

**Path:** `src/alita_sdk/community/eda/jira/jira_issues.py`

## Data Flow

The data flow within `jira_issues.py` revolves around extracting and transforming issues data from Jira. The data originates from the Jira API, where it is fetched using JQL (Jira Query Language) queries. The data is then processed and transformed into a pandas DataFrame, which includes calculated times for each issue's status and additional information such as release dates.

The data flow can be summarized as follows:
1. **Data Extraction:** Issues data is extracted from Jira using JQL queries. The data includes both default and custom fields.
2. **Data Transformation:** The extracted data is transformed to include calculated times for each issue's status and additional information such as release dates.
3. **Data Merging:** The transformed data is merged with historical data to create a comprehensive DataFrame.
4. **Data Filtering:** The data is filtered based on specific criteria, such as closed issues and release dates.

Example:
```python
# Extract data
 data_jira_fin, df_versions = self.extract_issues_from_jira(custom_fields, dates)
# Merge with calculated time that every issue spends in every status
df_time_in_status = lead_time_distribution_jira(data_jira_fin)
data_jira = merge_issues_and_history(data_jira_fin, df_time_in_status).reset_index(drop=True)
```

## Functions Descriptions

### `__init__`

The `__init__` method initializes the `JiraIssues` class with the necessary parameters, including the Jira instance, project keys, closed issues parameters, and defects name. It validates the `closed_issues_based_on` parameter to ensure it is either 1 or 2.

### `extract_issues_from_jira_and_transform`

This method extracts issues from Jira and transforms the data to include calculated times for each issue's status and additional information such as release dates. It returns a tuple containing the transformed data and a DataFrame with status order information.

### `extract_issues_from_jira`

This method extracts issues data from Jira based on the provided custom fields and dates. It constructs JQL queries to fetch both closed and open issues and merges the results into a single DataFrame.

### `_request_data_from_jira`

This method requests data from Jira using the provided JQL query and fields. It handles errors and retries the request if necessary.

### `_loop_jira_search`

This method performs a paginated search for issues in Jira using the provided JQL query and fields. It uses a thread pool to parallelize the data extraction process.

### `_get_data_jira_one_issue`

This method extracts data for a single Jira issue, including its changelog and custom fields.

### `_get_defects_data`

This method filters the extracted data to include only defects created after a specified date.

### `_add_request_type`

This method adds a new column to the DataFrame with the request type (closed, open, or defect).

### `_construct_jql_request`

This method constructs a JQL query based on the provided dates and request type (closed or open).

### `_list_jira_fields`

This method creates a string containing all the fields that need to be extracted from Jira.

### `_add_changelog`

This method adds the changelog data to the issue data.

### `_get_all_fields_values_for_issue`

This method extracts values for all requested fields (standard and custom) for a single Jira issue.

### `_get_default_issues_fields`

This method extracts standard fields values for a single Jira issue.

### `_concat_latest_versions`

This method concatenates the latest fix version data for a single issue with the DataFrame containing all latest fix versions.

### `_get_linked_issues`

This method extracts linked issues for a single Jira issue.

### `_get_latest_fix_version_for_issue`

This method extracts the latest fix version data for a single Jira issue.

### `_get_custom_fields_values`

This method extracts custom fields values for a single Jira issue.

### `_get_issues_changelog`

This method extracts the changelog for a single Jira issue.

## Dependencies Used and Their Descriptions

### `concurrent.futures`

Used for parallelizing the data extraction process using a thread pool.

### `warnings`

Used to filter out warnings.

### `logging`

Used for logging information and errors.

### `pandas`

Used for data manipulation and analysis.

### `retry`

Used to retry requests in case of errors.

### `jira`

Used to interact with the Jira API.

### `..utils.convert_to_datetime`

Used to convert strings to datetime objects.

### `..utils.transform_jira`

Contains various utility functions for transforming Jira data.

### `..utils.circuit_breaker`

Used to implement a circuit breaker pattern to handle errors.

### `..jira_fields`

Contains utility functions for handling Jira fields.

### `..jira_basic`

Contains basic functionality for interacting with Jira.

## Functional Flow

The functional flow of `jira_issues.py` involves initializing the `JiraIssues` class, extracting issues data from Jira, transforming the data, and merging it with historical data. The process includes handling errors and retries, parallelizing data extraction, and filtering the data based on specific criteria.

1. **Initialization:** The `JiraIssues` class is initialized with the necessary parameters.
2. **Data Extraction:** Issues data is extracted from Jira using JQL queries.
3. **Data Transformation:** The extracted data is transformed to include calculated times for each issue's status and additional information such as release dates.
4. **Data Merging:** The transformed data is merged with historical data to create a comprehensive DataFrame.
5. **Data Filtering:** The data is filtered based on specific criteria, such as closed issues and release dates.

Example:
```python
# Initialize the class
jira_issues = JiraIssues(jira, projects, closed_params, defects_name)
# Extract and transform data
 data_jira, df_map = jira_issues.extract_issues_from_jira_and_transform(custom_fields, dates)
```

## Endpoints Used/Created

### Jira API

The `jira_issues.py` file interacts with the Jira API to extract issues data. The endpoints used include:

- **Search Issues:** `jira.search_issues(jql_query, startAt, maxResults, fields, expand)`

This endpoint is used to search for issues in Jira based on the provided JQL query. The `startAt` and `maxResults` parameters are used for pagination, and the `fields` and `expand` parameters specify the fields to be included in the response.

Example:
```python
jira_search = self.jira.search_issues(jql_query, startAt=block['size'] * block['num'],
                                      maxResults=block['size'], fields=fields, expand="changelog")
```