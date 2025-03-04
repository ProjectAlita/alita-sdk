# transform_jira.py

**Path:** `src/alita_sdk/community/eda/utils/transform_jira.py`

## Data Flow

The data flow within `transform_jira.py` is centered around the transformation and analysis of Jira issue data. The file processes data from Jira issues, focusing on extracting and transforming various fields, calculating metrics, and preparing data for further analysis. The data originates from Jira issue exports, which are typically in the form of data frames. These data frames are manipulated through a series of functions that extract specific fields, calculate metrics, and transform the data into a format suitable for analysis.

For example, the function `get_field_value` extracts values from custom fields in the issues data frame:

```python
# Function to extract field value from custom field string

def get_field_value(field) -> str:
    if isinstance(field, dict):
        if 'value' in field.keys():
            return field['value']
        if 'name' in field.keys():
            return field['name']
    elif isinstance(field, list):
        return ','.join([get_field_value(f) for f in field])
    elif isinstance(field, str):
        opts = {'value=': ',', 'name=': ',', '\'value\': \'': '\',', '\'name\': \'': '\','}
        for opt, sep in opts.items():
            if opt in field:
                names = [name.split(sep)[0] for name in field.split(opt)[1:]]
                return ','.join(names)
    return field
```

This function takes a field, which can be a dictionary, list, or string, and extracts the relevant value. The extracted values are then used in further transformations and calculations.

## Functions Descriptions

### get_field_value

This function extracts the value from a custom field string in the issues data frame. It handles different types of fields, including dictionaries, lists, and strings. The function returns the extracted value as a string.

### fix_columns_values

This function fixes the values of specified columns in the issues data frame by applying the `get_field_value` function to each column. It takes a data frame and a list of column names as input and returns the modified data frame.

### _get_subtasks

This function extracts subtasks from the issues changelog. It takes a data frame of issues as input and returns a list of subtasks.

### _get_changelog_for_original_value

This function adds to the changelog values that were made on the issue creation. It takes a data frame of issues, a column name, and a changelog data frame as input and returns the modified changelog data frame.

### get_sprints_changelog

This function extracts the sprints changelog from the issues changelog. It takes a data frame of issues as input and returns a data frame of sprints changelog.

### get_story_points_changelog

This function extracts the story points changelog from the issues changelog. It takes a data frame of issues as input and returns a data frame of story points changelog.

### _calculate_sprint_changes

This function calculates rows for each sprint change and identifies the sprint change type (removed or added). It takes a data frame of sprints changelog as input and returns the modified data frame.

### _merge_sprint_and_changelog

This function calculates sprint start and end dates and merges sprint data with sprint changelog. It takes data frames of sprints and sprints changelog, and a buffer time as input and returns the merged data frame.

### _calculate_sprints_issues

This function calculates the number of issues in a sprint, which were committed, completed, and added during the sprint. It takes a series of issues and an optional buffer time as input and returns a series of calculated metrics.

### _calculate_sprints_story_points

This function calculates the story points for issues in a sprint. It takes a series of issues and an optional buffer time as input and returns a series of calculated story points.

### calculate_sprint_metrics

This function calculates metrics for sprints based on the issues sprint changelog and sprints data. It takes data frames of issues and sprints, and an optional buffer time as input and returns a data frame of calculated metrics.

### lead_time_distribution_jira

This function takes the Jira output data frame with issues, transforms it, and calculates the time each issue spends in each status. It returns a data frame with the transformed data.

### statuses_order_jira

This function takes the transformed data frame by the function `lead_time_distribution_jira` with issues changelog and returns a data frame with statuses indexes and count of every historical status for every issue.

### merge_issues_and_history

This function merges issues data without duplicates with transformed statuses' history. It takes data frames of issues and time in status as input and returns the merged data frame.

### copy_to_resolution_date

This function copies the last status change date to the field 'resolved_date' for JQL request for closed issues, which is built based on the issues' field 'status'. It takes data frames of time in status and issues, and a closed status string as input and returns the modified data frame.

### map_release_as_status

This function adds waiting for release to the statuses' mapping after Jira issues data has been extracted. It takes data frames of issues and statuses mapping as input and returns the modified statuses mapping data frame.

### define_index_for_release

This function defines the index for the pseudo-status 'Waiting for release' as the maximum statuses index plus one. It takes a data frame of statuses mapping as input and returns the index as a string.

### add_releases_info

This function adds to the issues' data, which have calculated time every issue spends in every status, waiting time for the latest release. The column 'status_history' is populated with pseudo-status 'Waiting for release'. It takes data frames of issues and versions as input and returns the modified data frame.

### merge_jira_and_versions_data

This function merges issues data with versions, calculates the time between issues resolution date and related fix versions release dates, drops columns, and copies data from the column resolved_date to the from_date. It takes data frames of issues and versions as input and returns the merged data frame.

### transform_versions_data

This function filters the data frame with fix versions data, adds a prefix 'version_' to the columns' names, adds a new column with 'Waiting for release' values, and converts string values of version_releaseDate to the datetime format. It takes a data frame of versions as input and returns the modified data frame.

### get_days_between

This function finds the number of days between dates in a data frame row. It takes a row, a start date string, and an end date string as input and returns the number of days as a float.

## Dependencies Used and Their Descriptions

### pandas

The `pandas` library is used extensively for data manipulation and analysis. It provides data structures like DataFrame, which are used to store and manipulate tabular data. In this file, `pandas` is used to handle Jira issue data, perform group operations, merge data frames, and apply transformations.

### numpy

The `numpy` library is used for numerical operations. It provides support for arrays and mathematical functions. In this file, `numpy` is used to handle missing values and perform numerical calculations.

### datetime

The `datetime` module is used to handle date and time operations. It provides classes for manipulating dates and times. In this file, `datetime` is used to calculate time differences and handle date conversions.

### convert_to_datetime

The `convert_to_datetime` module is a custom utility that provides functions to convert string values to datetime objects. It is used in the `transform_versions_data` function to convert version release dates to datetime format.

### constants

The `constants` module is a custom utility that provides constant values used throughout the file. It includes constants like `DATE_UTC`, `WAITING_FOR_RELEASE_STATUS`, `ACTIVE_STATUSES`, and `STATUSES_NOT_IN_CYCLE_TIME`.

## Functional Flow

The functional flow of `transform_jira.py` involves a series of steps to transform and analyze Jira issue data. The process starts with extracting and transforming specific fields from the issues data frame. The data is then processed to calculate metrics like sprint changes, story points, and lead time distribution. The transformed data is further analyzed to generate insights and prepare it for visualization or reporting.

For example, the `calculate_sprint_metrics` function orchestrates the calculation of sprint metrics:

```python
# Function to calculate metrics for sprints

def calculate_sprint_metrics(
        df_issues: pd.DataFrame, df_sprints: pd.DataFrame,
        buffer_time: timedelta = timedelta(0)) -> pd.DataFrame:
    if df_issues.empty:
        return pd.DataFrame()

    # Get sprints and story_points changelogs
    sprints_changelog = get_sprints_changelog(df_issues)
    story_points_changelog = get_story_points_changelog(df_issues)

    # create rows for each sprint change and identify change type (removed or added)
    sprints_changelog = _calculate_sprint_changes(sprints_changelog)

    # create rows for each issue_type and team for each sprint
    unique_rows = sprints_changelog[['team', 'issue_type', 'sprint_changed']].dropna().drop_duplicates()
    sprints = pd.merge(
        df_sprints, unique_rows, how='inner', left_on='name', right_on='sprint_changed').reset_index(drop=True)

    # add sprints start and end dates to the changelog
    sprints_changelog = _merge_sprint_and_changelog(sprints, sprints_changelog, buffer_time)

    # calculate issue metrics
    sprints_issues = sprints_changelog.groupby(['project_key', 'team', 'issue_type', 'name']).apply(
        _calculate_sprints_issues, buffer_time).reset_index()
    sprints = pd.merge(
        sprints, sprints_issues, how='left', on=['project_key', 'team', 'issue_type', 'name']).reset_index(drop=True)

    # add sprint details to story points changelog and calculate story points metrics
    sprints_changelog = sprints_changelog.rename(columns={'changelog_date': 'sprint_changelog_date'})
    story_points_changelog = pd.merge(
        sprints_changelog[['name', 'sprint_start', 'sprint_end', 'sprint_changed',
                           'issue_key', 'change_type', 'sprint_changelog_date']],
        story_points_changelog, how='inner', on='issue_key').reset_index(drop=True)
    story_points_changelog = story_points_changelog.drop_duplicates()
    sprint_story_points = story_points_changelog.groupby(['project_key', 'team', 'issue_type', 'name']).apply(
        _calculate_sprints_story_points, buffer_time).reset_index()
    sprints = pd.merge(
        sprints, sprint_story_points, how='left',
        on=['project_key', 'team', 'issue_type', 'name']).reset_index(drop=True)

    return sprints.drop_duplicates()
```

This function coordinates the extraction of sprints and story points changelogs, calculates sprint changes, merges sprint data with changelog, and computes metrics for issues and story points.

## Endpoints Used/Created

The `transform_jira.py` file does not explicitly define or call any endpoints. Its primary focus is on data transformation and analysis within the context of Jira issue data. The data is processed locally within the functions, and no external API calls or endpoints are involved in the operations.