"""This is a main module for time triggered data extraction from Jira."""
import logging
from typing import Optional
from datetime import datetime

import pandas as pd

from ...sql_tools.db_engine import DBEngine

from ...utils.read_config import Config
from ...jira.jira_connect import connect_to_jira
from ...jira.jira_issues import JiraBasic
from ...jira.jira_issues import JiraIssuesUpdate
from ...jira.jira_sprints import JiraSprints


class ExtractJiraIssuesToDb:
    """
    A class to run pipeline, which gets configuration parameters, extracts updated issues data from Jira and uploads
    it to the SQL DataBase.

    Attributes:
        jira_conf_path: str
            a path to the local file with configuration parameters for the data extraction (e.g. Jira projects lists,
            issues final status in their flow etc.).
        cloud_conf_path: str
            a path to the local file with configuration parameters for AWS or Azure services (DataBase, Secret Manager).
        jira_extraction_conf:
            configuration parameters for data extraction.
        cloud_provider_conf:
            configuration parameters of a cloud service.
        """

    def __init__(self, jira_conf_path: str, cloud_conf_path: str, cloud_provider: str):
        self.jira_conf_path = jira_conf_path
        self.cloud_conf_path = cloud_conf_path
        self.cloud_provider = cloud_provider
        self.jira_extraction_conf = Config.read_config(self.jira_conf_path)['Jira_params']
        self.cloud_provider_conf = Config.read_config(self.cloud_conf_path)

    def run_issues_pipeline(self, issues_table: str, deleted_issues_table: str) -> None:
        """Run the pipeline to extract data from Jora and save it to the DataBase."""
        data_extraction_date = datetime.utcnow()
        db_jira = DBEngine(self.cloud_conf_path, self.cloud_provider)
        for project in self.jira_extraction_conf['projects'].split(','):
            logging.info('Started the pipeline for the Jira project %s.', project)
            date_after = self._define_date_for_jql_query(
                db_jira, project, 'last_updated_date', issues_table)
            custom_fields = self.jira_extraction_conf[project]['custom_fields']

            df_issues = self._extract_updated_issues(project, custom_fields, date_after)

            df_issues['data_extraction_date'] = data_extraction_date
            ids_in_database = db_jira.get_field_unique_values(
                issues_table, 'issue_key', f"project_key='{project}'")
            deleted_ids = self._define_deleted_issues(project, ids_in_database)  # can be empty list
            if deleted_ids:
                logging.info('Deleted issues in Jira will be removed from the DataBase (%s)',
                             ','.join(deleted_ids))
            intersect_ids = self._define_issues_intersection(df_issues, ids_in_database)
            if ids_in_database:
                df_deleted = db_jira.select_and_upload_to_df(issues_table,
                                                             self._construct_delete_or_move_query(deleted_ids))
                db_jira.del_rows(issues_table, self._construct_delete_or_move_query(deleted_ids + intersect_ids))
                db_jira.write_to_db(df_deleted, deleted_issues_table, 'append')

            if not df_issues.empty:
                db_jira.write_to_db(df_issues, issues_table, 'append')
                logging.info('Jira data has been written to the DataBase.')

    def run_sprints_pipeline(self, sprints_table: str) -> None:
        """Run the pipeline to extract sprints data from Jira and save it to the DataBase."""
        jira = connect_to_jira(self.cloud_provider, self.cloud_conf_path)
        db_jira = DBEngine(self.cloud_conf_path, self.cloud_provider)
        df_sprints_all = pd.DataFrame()
        for project in self.jira_extraction_conf['projects'].split(','):
            logging.info('Started the sprints data extraction for the Jira project %s.', project)
            jira_sprints = JiraSprints(jira, project)
            df_sprints = jira_sprints.sprints_all_data_to_dataframe()
            df_sprints_all = pd.concat([df_sprints_all, df_sprints])
            logging.info('Sprints data from Jira project %s has been extracted.', project)
        db_jira.write_to_db(df_sprints_all, sprints_table, 'replace')

    def _extract_updated_issues(self, project: str, custom_fields: dict, date_after: str) -> pd.DataFrame:
        """
        Extract issues from Jira for one project, which were updated on or after the latest issues updated date in the
        AWS Database, or, if there is no issues in the DataBase,  on or after the date from the configuration file.
        """
        jira = connect_to_jira(self.cloud_provider, self.cloud_conf_path)
        jira_issues = JiraIssuesUpdate(jira, project,
                                       (self.jira_extraction_conf[project]['closed_issues_based_on'],
                                        self.jira_extraction_conf[project]['closed_status']),
                                       self.jira_extraction_conf[project]['defects_name'])
        df_issues, _ = jira_issues.extract_issues_from_jira_and_transform(custom_fields, tuple([date_after] * 3))
        logging.info('New data from Jira project %s has been extracted.', project)
        return df_issues

    def _define_date_for_jql_query(self, db_instance: DBEngine, project: str,
                                   column_name: str, issues_table: str) -> str:
        """Define date for issues extraction, after which they were updated."""
        last_updated_list = db_instance.get_field_unique_values(
            issues_table, column_name, f"project_key='{project}'")
        if last_updated_list:
            date_after = last_updated_list[0][:10]
            logging.info('Got the latest updated date %s for the %s', date_after, project)
        else:
            date_after = self.jira_extraction_conf['date_after']
            logging.info('Got the date %s date for the %s from the config file.', project, date_after)
        return date_after

    def _construct_delete_or_move_query(self, ids_list: list) -> Optional[str]:
        """
        Construct an SQL query to delete issues data from the SQL DataBase for issues, which are no longer
        exists in Jira itself or these issues are present in the newly extracted data from Jira.
        """
        deleted_and_newly_extracted = ids_list
        if len(deleted_and_newly_extracted) == 0:
            return None
        delete_string = self._construct_string(deleted_and_newly_extracted)
        return f'issue_key in ({delete_string})'

    @staticmethod
    def _construct_string(values_list: list) -> str:
        """Construct a string from a list of values."""
        result_string = ''
        for index, value in enumerate(values_list):
            if index != len(values_list) - 1:
                result_string += f"'{value}', "
            else:
                result_string += f"'{value}'"
        return result_string

    def _define_deleted_issues(self, project: str, ids_in_database: list) -> list:
        """Define issues deleted form Jira."""
        jira = connect_to_jira(self.cloud_provider, self.cloud_conf_path)
        jira_basic = JiraBasic(jira, project)
        existing_ids = jira_basic.get_issues_ids(self.jira_extraction_conf['date_after'])
        if not existing_ids:
            return []
        return [item for item in ids_in_database if item not in existing_ids]

    @staticmethod
    def _define_issues_intersection(df_issues, ids_in_database: list) -> list:
        """Define issues that are both in DataBase and newly extracted data from Jira."""
        if df_issues.empty:
            return []
        ids_new_extraction = df_issues['issue_key'].tolist()
        return [i for i in ids_in_database if i in ids_new_extraction]
