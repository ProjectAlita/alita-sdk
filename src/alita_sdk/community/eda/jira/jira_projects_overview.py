"""This module connects to a Jira instance, gets the list of projects a user has access with number of issues,
  and saves the result to a CSV file."""

import logging
import pandas as pd

from jira import JIRA, JIRAError

from .jira_connect import connect_to_jira_and_print_projects
from ..utils.constants import OUTPUT_ISSUES_COUNT

pd.set_option('display.max_rows', None)
pd.set_option('max_colwidth', 40)


def jira_projects_overview(after_date: str, project_keys: str, jira: JIRA) -> pd.DataFrame:
    """Get projects a user has access to and merge them with issues count."""
    jira, df_prj = connect_to_jira_and_print_projects(jira)
    projects_list = project_keys.strip().replace(" ", "").split(',')
    
    # Check if projects_list is present in df_prj['key'].tolist()
    available_projects = df_prj['key'].tolist()
    list_to_analyze = []
    for project in projects_list:
        if project not in available_projects:
            logging.warning(f"Project {project} is not available in the list of accessible projects.")
        else:
            list_to_analyze.append(project)
    
    df_count = jira_get_issues_count_for_projects(jira, list_to_analyze, after_date)
    if df_count.empty:
        logging.info("There are no issues in the requested projects")
        return df_prj

    df_result = pd.merge(df_prj, df_count, on='key', how='left')
    df_result = df_result[df_result['key'].isin(list_to_analyze)]
    df_result = df_result.sort_values(by='issues_count', ascending=False, ignore_index=True).reset_index(drop=True)
    df_result.to_csv(OUTPUT_ISSUES_COUNT, index=False)
    
    return df_result


def jira_get_issues_count_for_projects(jira: JIRA, rojects_to_analyze: list, after_date: str) -> pd.DataFrame:
    """Loop through every project and get issues count via JQL request."""
    projects_and_issues_num = {}

    for prj in rojects_to_analyze:
        jql = f'project = "{prj}" AND updated >= {after_date}'
        projects_and_issues_num[prj] = jira_get_issues_count(jira, jql)

    df_count = pd.DataFrame.from_dict(projects_and_issues_num, orient='index', columns=['issues_count'])
    df_count = df_count.reset_index()
    df_count = df_count.rename(columns={'index': 'key'})
    return df_count


def jira_get_issues_count(jira: JIRA, jql: str, block_size: int = 100, block_num: int = 0, fields: str = "key") -> int:
    """Request issues for one project which were updated after set date and return their number."""
    issues_num = 0
    try:
        jira_search = jira.search_issues(jql, startAt=block_num * block_size, maxResults=block_size, fields=fields)
        while jira_search:
            issues_num_one_block = len(jira_search)
            issues_num += issues_num_one_block
            block_num += 1
            jira_search = jira.search_issues(jql, startAt=block_num * block_size, maxResults=block_size, fields=fields)
        return issues_num
    except JIRAError as err:
        logging.error(f"Jira connection has been failed. Error: {err.status_code}, {err.text}")
        return issues_num
