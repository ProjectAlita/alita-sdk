"""This module gets all the statuses list in a Jira instance."""
from typing import Optional
from jira import JIRA
from .jira_connect import connect_to_jira


def get_all_statuses_list(jira: JIRA) -> Optional[list]:
    """Get all statuses names."""
    if not jira:
        jira = connect_to_jira()
    if not jira:
        raise ConnectionError('Failed to connect to Jira')
    statuses = jira.statuses()
    return [status.name for status in statuses]
    
