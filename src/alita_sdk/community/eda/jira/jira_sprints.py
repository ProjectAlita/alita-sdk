"""This module extracts sprints data from Jira."""

import logging
from typing import Optional

import pandas as pd
from retry import retry

from jira import JIRAError, JIRA

from ..utils.convert_to_datetime import string_to_datetime
from .jira_basic import JiraBasic
from ..utils.circuit_breaker import CircuitBreaker, CircuitOpenException


class JiraSprints(JiraBasic):
    """
    A class to get sprints' data from Jira.

    Attributes:
        jira: JIRA
            an instance of the JIRA class
        projects: str
            one or more projects keys separated with comma
        board_type: str
            type of Jira board.
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
        super().__init__(jira, projects)
        self.board_type = 'scrum'

    def sprints_all_data_to_dataframe(self) -> pd.DataFrame:
        """Extract sprints data from Jira for several projects."""
        projects_list = self.projects.strip().replace(" ", "").split(',')
        df_sprints = pd.DataFrame()
        for project in projects_list:
            boards = self._get_boards(board_type=self.board_type, project=project)
            boards_ids = self._get_boards_ids(boards)
            if not boards_ids:
                return pd.DataFrame()
            df_sprints = self._sprints_data_one_project_to_dataframe(boards_ids, project, df_sprints)
        return df_sprints

    @retry((JIRAError, CircuitOpenException), tries=4, delay=5, backoff=2)
    @CircuitBreaker(max_failures=3, reset_timeout=5)
    def _get_boards(self, board_type: str = None,
                    board_name: str = None, project: str = None) -> list:
        """Extract boards from Jira for one project."""
        boards_list = []
        try:
            start_at = 0
            max_results = 50
            boards_batch = self.jira.boards(start_at, max_results, self.board_type, board_name, project)
            while boards_batch:
                boards_list.extend(boards_batch)
                start_at += max_results
                boards_batch = self.jira.boards(start_at, max_results, board_type, board_name, project)
        except JIRAError as err:
            logging.error(err.text)
        return boards_list

    def _get_boards_ids(self, boards: list) -> list:
        """Get boards' ids from boards objects' attributes."""
        if not boards:
            logging.info(f"There are no scrum boards in the projects {self.projects}")
            return []
        boards_params = [board.raw for board in boards]
        return [params.get('id') for params in boards_params]

    def _sprints_data_one_project_to_dataframe(self, boards_ids: list, project: str,
                                               df_sprints_all_projects: pd.DataFrame) -> pd.DataFrame:
        """Get sprints data for one project and concatenate it with input DataFrame."""
        sprints_list = [self._get_sprints(board_id) for board_id in boards_ids]
        sprints_list = [item for sublist in sprints_list for item in sublist]
        df_sprints = self._get_sprints_info(sprints_list)
        df_sprints['project_key'] = project
        date_cols = [col for col in df_sprints.columns if 'Date' in col]
        df_sprints[date_cols] = df_sprints[date_cols].map(string_to_datetime)
        return pd.concat([df_sprints_all_projects, df_sprints], ignore_index=True)

    @retry((JIRAError, CircuitOpenException), tries=4, delay=5, backoff=2)
    @CircuitBreaker(max_failures=3, reset_timeout=5)
    def _get_sprints(self, board_id: int, extended: Optional[bool] = None, state: str = None) -> list:
        """Extract sprints from Jira."""
        sprints_list = []
        start_at = 0
        max_results = 50
        try:
            sprints_batch = self.jira.sprints(board_id, extended, start_at, max_results, state)
            while sprints_batch:
                sprints_list += sprints_batch
                start_at += max_results
                sprints_batch = self.jira.sprints(board_id, extended, start_at, max_results, state)
        except JIRAError as err:
            logging.error(err.text)
        return sprints_list

    @staticmethod
    def _get_sprints_info(sprints_list: list) -> pd.DataFrame:
        """Get sprints data from sprints objects' attributes and put it to the DataFrame."""
        if not sprints_list:
            return pd.DataFrame()
        sprints_info = [sprint.raw for sprint in sprints_list]
        return pd.DataFrame.from_records(sprints_info)
