"""A module to get issues data from all Jira fields."""
import logging
from typing import Optional
import pandas as pd

from jira import JIRAError, JIRA


class JiraBasic:
    """
    A class to get issues data from all Jira fields.

    Attributes:
        jira: JIRA
            an instance of the JIRA class
        projects: str
            one or more projects keys separated with comma.
    """

    def __init__(self, jira: JIRA, projects: str):
        """
        Initialize the class with jira and projects parameters.
        Args:
            jira: JIRA
                an instance of the JIRA class
            projects: str
                one or more projects keys separated with comma
        """
        self.jira = jira
        self.projects = projects
        if not self.projects:
            raise ValueError('Please, specify projects keys!')

    def get_issues_ids(self, updated_after: str) -> Optional[list]:
        """Get the list of ids of the issues that were updated after the defined date."""
        fields = 'key'
        df_issues = self.extract_all_fields(updated_after, fields)
        if df_issues.empty:
            return None
        return df_issues['key'].tolist()

    def extract_all_fields(self, updated_after: str, fields: str = None, block_size: int = 100,
                           block_num: int = 0) -> Optional[pd.DataFrame]:
        """Extract issues with all Jira fields."""
        parameters = {
            'jql_str': f'project IN ({self.projects}) AND updated >= {updated_after}',
            'startAt': block_num * block_size,
            'maxResults': block_size,
            'json_result': True,
        }
        if fields:
            parameters['fields'] = fields
        return self._extract_fields_values(parameters)

    def _extract_fields_values(self, parameters: dict, block_size: int = 100,
                               block_num: int = 0) -> Optional[pd.DataFrame]:
        """
        Extract issues from Jira. Jira fields and other parameters
        (e.g. jql_str, startAt, maxResults) should be defined.
        """
        if not self.jira:
            return None
        issues_data = []
        df_issues = pd.DataFrame()
        blocks_per_log = 50
        try:
            jira_search = self.jira.search_issues(**parameters).get('issues')
            while jira_search:
                parameters['startAt'] = block_size * block_num
                issues_data += jira_search
                block_num += 1
                if block_num % blocks_per_log == 0:
                    logging.info(block_num * block_size)
                jira_search = self.jira.search_issues(**parameters).get('issues')
            df_issues = pd.json_normalize(issues_data)
        except JIRAError as error:
            logging.error(error.status_code, error.text)
        return df_issues
