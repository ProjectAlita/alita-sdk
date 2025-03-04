# transform_jira.py

**Path:** `src/alita_sdk/community/eda/utils/transform_jira.py`

## Data Flow

The data flow within `transform_jira.py` revolves around the transformation and analysis of Jira issue data. The primary data source is a DataFrame containing Jira issues, which undergoes various transformations to extract meaningful metrics and insights. The data journey begins with the extraction of field values from custom fields, followed by fixing column values in the issues DataFrame. Subtasks are then extracted from the issues changelog, and original values are added to the changelog for issues created with initial values. The data is further processed to extract sprints and story points changelogs, calculate sprint changes, and merge sprint data with the changelog. Metrics for sprints are calculated based on the issues sprint changelog and sprints data. The lead time distribution for Jira issues is calculated, and the statuses order is determined. The issues data is merged with the transformed statuses' history, and the last status change date is copied to the resolved date for closed issues. Finally, waiting time for the latest release is added to the issues' data, and the issues data is merged with versions data to calculate the time between issues resolution date and related fix versions release dates.

Example:
```python
# Extract field value from the custom field string in the issues dataframe
field_value = get_field_value(field)

# Fix columns values in the issues dataframe
fixed_df = fix_columns_values(df_issues, columns)

# Extract subtasks from the issues changelog
subtasks = _get_subtasks(df_issues)

# Add to changelog values that were made on the issue creation
changelog = _get_changelog_for_original_value(df_issues, column, changelog)
```

## Functions Descriptions

### get_field_value(field) -> str

Extracts field value from the custom field string in the issues DataFrame. It handles basic cases where the field is a dictionary, list, or string. If the field is a dictionary, it returns the value associated with the 'value' or 'name' key. If the field is a list, it recursively extracts values from each element. If the field is a string, it parses the string to extract values based on predefined separators.

### fix_columns_values(df_issues: pd.DataFrame, columns: list[str]) -> pd.DataFrame

Fixes columns values in the issues DataFrame by applying the `get_field_value` function to each specified column. It iterates over the columns and applies the function to each value, resetting the index of the DataFrame.

### _get_subtasks(df_issues: pd.DataFrame) -> list

Extracts subtasks from the issues changelog. It fills missing values in the DataFrame, filters out rows with empty subtasks, splits the subtasks string, and explodes the list into individual subtasks.

### _get_changelog_for_original_value(df_issues: pd.DataFrame, column: str, changelog: pd.DataFrame) -> pd.DataFrame

Adds to the changelog values that were made on the issue creation. It identifies issues not present in the changelog but with values added at creation and issues with values at creation. It merges these new rows with the existing changelog.

### get_sprints_changelog(df_issues: pd.DataFrame) -> pd.DataFrame

Extracts sprints changelog from the issues changelog. It filters out subtasks, fills missing values, and extracts rows related to sprint changes. It adds original values to the changelog and removes duplicate rows.

### get_story_points_changelog(df_issues: pd.DataFrame) -> pd.DataFrame

Extracts story points changelog from the issues changelog. It filters out subtasks, fills missing values, and extracts rows related to story points changes. It adds original values to the changelog and removes duplicate rows.

### _calculate_sprint_changes(sprints_changelog: pd.DataFrame) -> pd.DataFrame

Calculates rows for each sprint change and identifies the sprint change type (removed or added). It applies symmetric difference to identify changes and explodes the list into individual changes.

### _merge_sprint_and_changelog(df_sprints: pd.DataFrame, sprints_changelog: pd.DataFrame, buffer_time: timedelta) -> pd.DataFrame

Calculates sprint start and end dates and merges sprint data with sprint changelog. It selects the last change before the sprint start and concatenates it with the remaining changelog.

### _calculate_sprints_issues(issues_group: pd.Series, buffer_time: timedelta = timedelta(0)) -> pd.Series

Calculates the number of issues in a sprint that were committed, completed, and added during the sprint. It filters issues based on change type and changelog date and counts unique issue keys.

### _calculate_sprints_story_points(issues_group: pd.Series, buffer_time: timedelta = timedelta(0)) -> pd.Series

Calculates the story points for issues in a sprint that were committed, completed, added, and removed during the sprint. It filters issues based on change type, changelog date, and story points values.

### calculate_sprint_metrics(df_issues: pd.DataFrame, df_sprints: pd.DataFrame, buffer_time: timedelta = timedelta(0)) -> pd.DataFrame

Calculates metrics for sprints based on the issues sprint changelog and sprints data. It extracts sprints and story points changelogs, calculates sprint changes, merges sprint data with changelog, and calculates issue and story points metrics.

### lead_time_distribution_jira(df_issues: pd.DataFrame) -> pd.DataFrame

Takes the Jira output DataFrame with issues, transforms it, and calculates the time each issue spends in each status. It filters out defects and changelog not related to status changes, sorts by changelog date, and calculates time in status for each issue.

### statuses_order_jira(df_issues: pd.DataFrame) -> pd.DataFrame

Takes the transformed DataFrame by the function `lead_time_distribution_jira` with issues changelog and returns a DataFrame with statuses indexes and count of every historical status for every issue.

### merge_issues_and_history(data_jira_fin: pd.DataFrame, time_in_status_df: pd.DataFrame) -> pd.DataFrame

Merges issues data without duplicates with transformed statuses' history. It drops duplicates, merges with time in status DataFrame, and returns the merged DataFrame.

### copy_to_resolution_date(time_in_status_df: pd.DataFrame, data_jira: pd.DataFrame, closed_status: str) -> pd.DataFrame

Copies the last status change date to the field 'resolved_date' for JQL request for closed issues, which is built based on the issues' field 'status'.

### map_release_as_status(df_issues: pd.DataFrame, df_map: pd.DataFrame) -> pd.DataFrame

Adds waiting for release to the statuses' mapping after Jira issues data has been extracted. It creates a new row for the waiting for release status and concatenates it with the existing mapping.

### define_index_for_release(df_map: pd.DataFrame) -> str

Defines the index for the pseudo-status 'Waiting for release' as the maximum statuses index plus one.

### add_releases_info(data_jira_final: pd.DataFrame, df_versions: pd.DataFrame) -> pd.DataFrame

Adds to the issues' data, which have calculated time every issue spends in every status, waiting time for the latest release. It merges issues data with versions data and calculates the time between issues resolution date and related fix versions release dates.

### merge_jira_and_versions_data(data_jira: pd.DataFrame, data_versions) -> pd.DataFrame

Merges issues data with versions, calculates time between issues resolution date and related fix versions release dates, drops columns, and copies data from the column resolved_date to the from_date.

### transform_versions_data(df_versions: pd.DataFrame) -> pd.DataFrame

Filters DataFrame with fix versions data, adds prefix 'version_' to the columns' names, adds new column with 'Waiting for release' values, and converts string values version_releaseDate to the datetime format.

### get_days_between(row: pd.Series, start_date: str, end_date: str) -> float

Finds the number of days between dates in a DataFrame row. It calculates the difference between the start and end dates and returns the total number of days.

## Dependencies Used and Their Descriptions

### datetime

The `datetime` module supplies classes for manipulating dates and times. In this file, it is used to handle date and time operations, such as calculating the difference between dates and adding buffer time to sprint start dates.

### pandas

`pandas` is a powerful data analysis and manipulation library for Python. It is used extensively in this file to handle DataFrame operations, such as filtering, merging, and transforming data.

### numpy

`numpy` is a fundamental package for scientific computing in Python. It is used in this file for numerical operations, such as replacing missing values and calculating time differences.

### convert_to_datetime

The `convert_to_datetime` module is a custom utility that provides a function to convert string values to datetime format. It is used in this file to convert version release dates to datetime format.

### constants

The `constants` module is a custom utility that provides constant values used throughout the file, such as `DATE_UTC`, `WAITING_FOR_RELEASE_STATUS`, `ACTIVE_STATUSES`, and `STATUSES_NOT_IN_CYCLE_TIME`.

## Functional Flow

The functional flow of `transform_jira.py` begins with the extraction of field values from custom fields using the `get_field_value` function. The `fix_columns_values` function is then called to fix column values in the issues DataFrame. Subtasks are extracted from the issues changelog using the `_get_subtasks` function, and original values are added to the changelog using the `_get_changelog_for_original_value` function. The `get_sprints_changelog` and `get_story_points_changelog` functions are called to extract sprints and story points changelogs, respectively. Sprint changes are calculated using the `_calculate_sprint_changes` function, and sprint data is merged with the changelog using the `_merge_sprint_and_changelog` function. The `calculate_sprint_metrics` function is called to calculate metrics for sprints based on the issues sprint changelog and sprints data. The `lead_time_distribution_jira` function is called to calculate the time each issue spends in each status, and the `statuses_order_jira` function is called to determine the statuses order. The `merge_issues_and_history` function is called to merge issues data with the transformed statuses' history, and the `copy_to_resolution_date` function is called to copy the last status change date to the resolved date for closed issues. The `map_release_as_status` function is called to add waiting for release to the statuses' mapping, and the `define_index_for_release` function is called to define the index for the pseudo-status 'Waiting for release'. The `add_releases_info` function is called to add waiting time for the latest release to the issues' data, and the `merge_jira_and_versions_data` function is called to merge issues data with versions data and calculate the time between issues resolution date and related fix versions release dates. The `transform_versions_data` function is called to transform the versions data, and the `get_days_between` function is called to calculate the number of days between dates in a DataFrame row.

## Endpoints Used/Created

This file does not explicitly define or call any endpoints. The primary focus of the file is on transforming and analyzing Jira issue data within DataFrames. The data is processed and transformed using various functions, but no external endpoints are used or created within this file.
