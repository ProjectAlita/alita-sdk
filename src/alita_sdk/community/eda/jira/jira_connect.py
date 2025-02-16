"""
This module connects to Jira instance with user's credentials from config.yml,
gets projects list an authenticated user has access to and gets issues number for each project.
"""

import logging
from typing import Optional, Tuple
import pandas as pd
from jira import JIRA, JIRAError

from ..utils.read_config import JiraConfig, Config
from ..utils.constants import OUTPUT_PROJECTS_PATH

def connect_to_jira(
    jira_base_url: str,
    jira_verify_ssl: bool = True,
    jira_username: Optional[str] = None,
    jira_api_key: Optional[str] = None,
    jira_token: Optional[str] = None
) -> Optional[JIRA]:
    """
    Connects to Jira using provided credentials.
    """
    jira_options = {
        'verify': jira_verify_ssl
    }
    jira = JIRA(
        server=jira_base_url,
        options=jira_options,
        basic_auth=(jira_username, jira_api_key) if jira_api_key else None,
        token_auth=jira_token if jira_token else None
    )
    return jira


def connect_to_jira_and_print_projects(
    jira: JIRA = None,
    jira_base_url: str=None,
    jira_verify_ssl: bool = True,
    jira_username: Optional[str] = None,
    jira_api_key: Optional[str] = None,
    jira_token: Optional[str] = None
) -> Optional[Tuple[JIRA, pd.DataFrame]]:
    """Get information on all projects in Jira you have access to (their number, keys and names)."""
    if not jira:
        jira = connect_to_jira(
            jira_base_url=jira_base_url,
            jira_verify_ssl=jira_verify_ssl,
            jira_username=jira_username,
            jira_api_key=jira_api_key,
            jira_token=jira_token
        )
    if not jira:
        logging.error('Failed to connect to Jira')
        return None

    logging.info('You have connected to Jira')
    df_prj = pd.DataFrame()
    projects = jira.projects()
    prj_keys = []
    prj_names = []
    prj_num = len(projects)
    if prj_num:
        logging.info('You have access to the next %s projects:', prj_num)
        for prj in projects:
            prj_keys += [prj.key]
            prj_names += [prj.name]
        prj_info = {'key': prj_keys, 'name': prj_names}
        df_prj = create_df_from_dict_and_save(prj_info)
    else:
        logging.info("You don't have access to any project")
    return jira, df_prj


def create_df_from_dict_and_save(prj_info: dict) -> pd.DataFrame:
    """Create a dataframe with extracted information and save results to CSV file."""
    df_prj = pd.DataFrame.from_dict(prj_info)
    df_prj.index = df_prj.index + 1
    df_prj.to_csv(OUTPUT_PROJECTS_PATH, index=True)
    return df_prj
