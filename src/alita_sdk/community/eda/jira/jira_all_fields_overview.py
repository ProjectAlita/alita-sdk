"""This module calculates usage statistic of Jira fields for one or more projects."""

import re
import warnings
import logging
import pandas as pd

from jira import JIRA

from ..jira.jira_connect import connect_to_jira
from ..jira.jira_fields import JiraFields
from ..jira.jira_basic import JiraBasic
from ..utils.constants import OUTPUT_FOLDER, OUTPUT_COUNT_PATH


warnings.filterwarnings("ignore")

pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)
pd.set_option("expand_frame_repr", True)

DEFAULT_JIRA_COLUMNS = ['assignee.displayName', 'attachment', 'comment.comments', 'components', 'created',
                        'creator.displayName', 'description', 'fixVersions', 'issue_id', 'issue_key', 'issuelinks',
                        'issuetype.name', 'labels', 'lastViewed', 'priority.name', 'project.key', 'project.name',
                        'reporter.displayName', 'resolution.name', 'resolutiondate', 'status.name', 'subtasks',
                        'summary', 'updated', 'versions']


def jira_all_fields_overview(projects: str, updated_after: str, jira: JIRA=None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Extract all fields from Jira, filter out columns with all None values, calculate statistic on the fields' usage.
    """
    # Extract all fields values from Jira, filter and columns
    if jira is None:
        jiraBasic = JiraBasic(connect_to_jira(), projects)
    else:
        jiraBasic = JiraBasic(jira, projects)
    all_fields_data = jiraBasic.extract_all_fields(updated_after)
    all_fields_data = _rename_columns(all_fields_data)
    columns_filtered = _filter_columns(all_fields_data)
    filtered_columns_data = all_fields_data.filter(items=columns_filtered)
    name_pairs = _get_names_pairs(jira, filtered_columns_data)
    result_data = filtered_columns_data.rename(columns=name_pairs)
    result_data = result_data.map(lambda x: None if isinstance(x, list) and len(x) == 0 else x)
    result_data.columns = result_data.columns.str.replace('.', '_')

    # Calculate statistic for projects (all issue types)
    overall_stat = _describe_fields_values(result_data)

    # Calculate statistic per issue types
    issue_types_stat = _describe_fields_values_per_issue_type(result_data)
    logging.info(f'Look at the results here or open the file {OUTPUT_COUNT_PATH} in the folder {OUTPUT_FOLDER}')
    return overall_stat, issue_types_stat


def _rename_columns(df_issues: pd.DataFrame) -> pd.DataFrame:
    """Rename columns with issues' ids and keys and remove 'fields' in the beginning of columns' names"""
    df_issues = df_issues.rename(columns={'id': 'issue_id', 'key': 'issue_key'})
    df_issues.columns = df_issues.columns.str.replace('fields.', '')
    return df_issues


def _get_names_pairs(jira_connection: JIRA, df_issues: pd.DataFrame) -> dict:
    """Create a dictionary with fields ids and names."""
    jira_fields = JiraFields({})
    fields_list, _ = jira_fields.get_all_fields_list(jira_connection)
    columns_list = df_issues.columns.tolist()
    name_pairs = {}
    for field in fields_list:
        if field['id'] or f'{field["id"]}.value' in columns_list:
            name_pairs[field['id']] = field['name']
            name_pairs[f'{field["id"]}.value'] = field['name']
    return name_pairs


def _filter_columns(df_issues: pd.DataFrame) -> list:
    """Get a list of a dataframe column and filter it."""
    # Filter out columns, booleans for all the values in which are False
    df_issues = df_issues.loc[:, ~df_issues.where(df_issues.astype(bool)).isna().all(axis=0)]

    columns = df_issues.columns.tolist()
    columns_default = [column for column in columns if column in DEFAULT_JIRA_COLUMNS]
    columns_custom = [column for column in columns if re.search("^customfield.*", column)]
    columns = columns_default + columns_custom

    columns_filtered = [column for column in columns if not re.search(".*\\.self$", column)]
    columns_filtered = [column for column in columns_filtered if not re.search(".*\\.disabled$", column)]
    columns_filtered = [column for column in columns_filtered if not re.search(".*\\.id$", column)]
    return columns_filtered


def _describe_fields_values(issues_data: pd.DataFrame) -> pd.DataFrame:
    """Calculate statistic for the all Jira fields usage for the requested projects."""
    # Define parameters for writing data
    df_count = _count_values(issues_data)
    # Create data frame 'df_label' to label tables with data  in CSV
    df_label = pd.DataFrame({'id': ['PROJECTS OVERVIEW (ALL ISSUE TYPES)', '']}, index=[0, 1])
    # Write label and data to CSV
    df_label.to_csv(OUTPUT_COUNT_PATH, mode='w', header=False, index=False)
    df_count.to_csv(OUTPUT_COUNT_PATH, mode='a', header=True, index=True, index_label='Fields')
    logging.info(f'\nPROJECTS OVERVIEW (ALL ISSUE TYPES)\n\n{df_count}')
    return df_count


def _describe_fields_values_per_issue_type(issues_data: pd.DataFrame) -> pd.DataFrame:
    """Calculate statistic for the all Jira fields usage for the requested projects per issue type."""
    df_count = pd.DataFrame()
    for item in issues_data['issuetype_name'].unique():
        df_issue_type = issues_data[issues_data['issuetype_name'] == item]
        df_count = _count_values(df_issue_type)
        logging.info(f'\nISSUE TYPE {item}\n\n{df_count}\n')
        # Create data frame 'df_label' to label tables with data  in CSV
        df_label = pd.DataFrame({'id': ['', 'ISSUE TYPE', ''], 'text': ['', item, '']}, index=[0, 1, 2])
        # Write label and data to CSV
        df_label.to_csv(OUTPUT_COUNT_PATH, mode='a', header=False, index=False)
        df_count.to_csv(OUTPUT_COUNT_PATH, mode='a', header=True, index=True, index_label='Fields')
    return df_count


def _count_values(issues_data: pd.DataFrame) -> pd.DataFrame:
    """Group a dataframe by projects' names and count values in other columns."""
    df_count = issues_data.groupby(by='project_key').count().T
    df_count = _sort_by_sum_across_columns(df_count)
    df_count = df_count.map(lambda x: f'{x} ({round(x / len(issues_data) * 100, 1)}%)')
    return df_count


def _sort_by_sum_across_columns(df_data: pd.DataFrame) -> pd.DataFrame:
    """Sort a dataframe by th temporally added column with the sum of values across all columns."""
    df_count = df_data.loc[(df_data.sum(axis=1)).sort_values(ascending=False).index]
    return df_count
