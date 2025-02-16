"""This module that extracts issues data from Jira."""
import concurrent.futures

import warnings
from typing import Optional, Union
import logging

from collections import defaultdict

import pandas as pd
from retry import retry

from jira import JIRAError, Issue, JIRA

from ..utils.convert_to_datetime import string_to_datetime
from ..utils.transform_jira import (lead_time_distribution_jira, merge_issues_and_history, add_releases_info,
                                    copy_to_resolution_date, statuses_order_jira, map_release_as_status,
                                    get_field_value)
from ..utils.circuit_breaker import CircuitBreaker, CircuitOpenException
from .jira_fields import JiraFields
from .jira_basic import JiraBasic

warnings.filterwarnings("ignore")

DEFAULT_FIELDS_TO_EXTRACT = ('key, fixVersions, resolution, priority, labels, issuelinks, status, subtasks, '
                             'components, id, resolutiondate, issuetype, created, updated, summary, '
                             'aggregatetimespent, issuelinks, project, changelog, ')


class JiraIssues(JiraBasic):
    """
    A class to get issues data from Jira and create the resulted DataFrame.

    Attributes:
        jira: JIRA
            an instance of the JIRA class
        projects: str
            one or more projects keys separated with comma
        closed_issues_based_on: int
            1 - issues will be thought as closed based on their status
            2 - issues will be thought as closed if resolution date is not empty
        closed_status: str
            status name for closed issues if closed_issues_based_on ==  1.
        defects_name: str
            the name of a custom field for the environment where bugs/defects were registered.
    """

    def __init__(self, jira: JIRA, projects: str, closed_params: tuple[int, str],  # pylint: disable=too-many-arguments
                 defects_name: str, add_filter: str = ''):
        """
        Initialize the class with jira, projects, closed and defect names parameters.
        Args:
            jira: JIRA
                an instance of the JIRA class
            projects: str
                one or more projects keys separated with comma
            closed_params: tuple[int, str]
                (closed_issues_based_on, closed_status)
            defects_name: str
                the name of a custom field for the environment where bugs/defects were registered.
        """
        super().__init__(jira, projects)
        self.jira = jira
        self.closed_issues_based_on, self.closed_status = closed_params
        if self.closed_issues_based_on not in [1, 2]:
            raise ValueError('The value of "closed_issues_based_on" should be integer number 1 or 2')
        self.defects_name = defects_name
        self.add_filter = add_filter

    def extract_issues_from_jira_and_transform(self, custom_fields: dict, dates: tuple)\
            -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Extract issues from specific Jira fields and then transform it: add calculated time every issue spent in every
        status and waiting time for the latest release as a pseudo historical status.
        """
        # Extract data
        data_jira_fin, df_versions = self.extract_issues_from_jira(custom_fields, dates)
        # Merge with calculated time that every issue spends in every status
        df_time_in_status = lead_time_distribution_jira(data_jira_fin)
        data_jira = merge_issues_and_history(data_jira_fin, df_time_in_status).reset_index(drop=True)
        df_map = pd.DataFrame()
        if not df_time_in_status.empty:
            # If issues are thought to be closed based on the issues' status,
            # populate resolved_date with the latest status transition date
            if self.closed_issues_based_on == 1:
                data_jira = copy_to_resolution_date(df_time_in_status, data_jira, self.closed_status)
                # drop closed issues with resolved_date before requested resolved_after date
                data_jira = data_jira.loc[~((data_jira.status == self.closed_status) &
                                            (data_jira.resolved_date < dates[0]))]
            # Add information on releases to issues to calculate time between resolution date and release date
            data_jira = add_releases_info(data_jira, df_versions)
            data_jira = data_jira.sort_values(by=['issue_key', 'from_date'], ignore_index=True)
            df_map = statuses_order_jira(df_time_in_status)
            df_map = map_release_as_status(data_jira, df_map)

        return data_jira, df_map

    def extract_issues_from_jira(self, custom_fields: dict, dates: tuple[str, str, str]) \
            -> Optional[tuple[pd.DataFrame, pd.DataFrame]]:
        """Extract default and custom fields values and save results to CSV files."""
        if not self.jira:
            return None

        df_versions_fin = data_jira_fin = pd.DataFrame()
        resolved_after, updated_after, created_after = dates

        fields = self._list_jira_fields(custom_fields)
        for request_type in ['closed', 'open']:
            jql_query = self._construct_jql_request((resolved_after, updated_after), request_type)
            logging.info(jql_query)
            data_jira_one_req, df_versions = self._request_data_from_jira(custom_fields, fields, jql_query)
            data_jira_one_req = self._add_request_type(data_jira_one_req, request_type)
            data_jira_fin = pd.concat([data_jira_fin, data_jira_one_req], ignore_index=True)
            df_versions_fin = pd.concat([df_versions_fin, df_versions], ignore_index=True)

        data_jira_fin = pd.concat([data_jira_fin, self._get_defects_data(data_jira_fin, created_after)],
                                  ignore_index=True)
        return data_jira_fin, df_versions_fin

    def _request_data_from_jira(self, custom_fields: dict, fields, jql_query) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Request data from Jira and return the extracted DataFrame. If no data is found, close connection."""
        try:
            data_jira_one_req, df_versions = self._loop_jira_search(
                jql_query, fields, custom_fields)
            return data_jira_one_req, df_versions
        except JIRAError as err:
            logging.error('%s, %s', err.status_code, err.text)
            raise err

    @retry((JIRAError, CircuitOpenException), tries=4, delay=5, backoff=2)
    @CircuitBreaker(max_failures=3, reset_timeout=5)
    def _loop_jira_search(self, jql_query: Optional[str], fields: str, custom_fields: dict) \
            -> tuple[pd.DataFrame, pd.DataFrame]:
        """Search for issues with pagination."""
        block = {'size': 100, 'num': 0}

        if jql_query:
            jira_search = self.jira.search_issues(jql_query, startAt=block['size'] * block['num'],
                                                  maxResults=block['size'], fields=fields, expand="changelog")
        else:
            jira_search = None
            logging.info("You haven't defined issue types in the parameter 'defects_name'")

        if jql_query and not jira_search:
            logging.info('There are no issues fulfilling JQL %s', jql_query)

        df_versions = data_jira_one_req = pd.DataFrame()
        data_jira = []
        blocks_per_log = 50
        while jira_search:
            with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
                futures = [executor.submit(
                    self._get_data_jira_one_issue, (issue, custom_fields)) for issue in jira_search]
                for future in concurrent.futures.as_completed(futures):
                    data_jira_one_issue, df_versions_one_item = future.result()
                    df_versions = self._concat_latest_versions(df_versions, df_versions_one_item)
                    data_jira += data_jira_one_issue
            data_jira_one_req = pd.DataFrame.from_records(data_jira)
            block['num'] += 1
            if block['num'] % blocks_per_log == 0:
                logging.info(block['num'] * block['size'])
            jira_search = self.jira.search_issues(jql_query, startAt=block['size'] * block['num'],
                                                  maxResults=block['size'], fields=fields, expand="changelog")
        return data_jira_one_req, df_versions

    def _get_data_jira_one_issue(self, args_: tuple) -> tuple[list, Union[pd.DataFrame, pd.Series]]:
        """Get data jira issue and versions of one item."""
        issue, custom_fields = args_
        data_jira_one_issue, df_versions_one_item = self._get_all_fields_values_for_issue(issue, custom_fields)
        data_jira_one_issue = self._add_changelog(issue, data_jira_one_issue)
        return data_jira_one_issue, df_versions_one_item

    def _get_defects_data(self, data: pd.DataFrame, created_after: str) -> pd.DataFrame:
        """
        Get defects from extracted JIRA data that were created after the defined date.
        """
        if data.empty:
            return pd.DataFrame()
        defects_data = pd.DataFrame()
        if self.defects_name != '':
            defects_data = data.loc[(data.issue_type.isin(self.defects_name.split(','))) &
                                    (data.created_date >= string_to_datetime(created_after))]
            defects_data = self._add_request_type(defects_data, 'defect')

        return defects_data

    @staticmethod
    def _add_request_type(data_jira: pd.DataFrame, request_type: str) -> pd.DataFrame:
        """Add new column to the dataframe with issues data 'request_type' with values equal request type."""
        if not data_jira.empty:
            data_jira.loc[:, 'request_type'] = request_type
        return data_jira

    def _construct_jql_request(self, dates: tuple[str, str], request_type) -> Optional[str]:
        """
        Construct a set of JQL requests based on the input parameter 'closed_issues_based_on':
        1 - Closed issues are thought to be based on their status
        2 - Closed issues are thought to be based on the resolution date.
        """
        resolved_after, updated_after = dates
        base_query = f'project IN ({self.projects})'
        filter_query = f' AND {self.add_filter}' if self.add_filter != '' else ''

        conditions = {
            'closed': {
                1: f'status = {self.closed_status} AND updated >= {updated_after}',
                2: f'resolved is not EMPTY AND resolved >= {resolved_after}'
            },
            'open': {
                1: f'status != {self.closed_status} AND updated >= {updated_after}',
                2: f'resolved is EMPTY AND updated >= {updated_after}'
            }
        }

        if self.closed_issues_based_on in [1, 2] and request_type in ['closed', 'open']:
            jql_query = f'{base_query} AND {conditions[request_type][self.closed_issues_based_on]}{filter_query}'
        else:
            jql_query = None

        return jql_query

    def _list_jira_fields(self, custom_fields: dict) -> str:
        """Create a string, which contains all fields that are needed to be extracted."""
        custom_fields_id, _ = JiraFields(custom_fields).define_custom_fields_ids(self.jira)
        fields = DEFAULT_FIELDS_TO_EXTRACT + ', '.join([str(f) for f in custom_fields_id])
        return fields

    def _add_changelog(self, issue: Issue, data_one_issue: dict) -> list:
        """Add to the issue data it's changelog."""
        data_one_issue_with_changelog = []
        changelog = self._get_issues_changelog(issue)
        for value in changelog:
            data_one_issue_with_changelog.append(data_one_issue | value)
        return data_one_issue_with_changelog

    def _get_all_fields_values_for_issue(self, issue: Issue,
                                         custom_fields: dict) -> tuple[dict, Union[pd.DataFrame, pd.Series]]:
        """Get values for the all requested issues' fields in Jira (standard, custom)."""
        issue_id_and_key = {'issue_key': issue.raw.get('key'), 'issue_id': issue.raw.get('id')}

        issue_fields = issue.raw.get('fields')
        if not issue_fields:
            raise KeyError('There are no needed fields in Jira (e.g. project key, project name etc.)')

        standard_fields_values, df_versions_one_item = self._get_default_issues_fields(issue_fields)

        if not df_versions_one_item.empty:
            df_versions_one_item['issue_key'] = issue_id_and_key['issue_key']

        _, custom_fields_dict = JiraFields(custom_fields).define_custom_fields_ids(self.jira)
        custom_fields_values = self._get_custom_fields_values(issue_fields, custom_fields_dict)

        data_one_issue = issue_id_and_key | standard_fields_values | custom_fields_values

        return data_one_issue, df_versions_one_item

    def _get_default_issues_fields(self, issue_fields: dict) -> tuple:
        """Get Jira standard issues attributes for one issue."""
        issue_dict = {}
        project = issue_fields.get('project')
        if project:
            issue_dict['project_name'] = project.get('name')
            issue_dict['project_key'] = project.get('key')
        issue_dict['issue_type'] = issue_fields.get('issuetype').get('name')
        issue_dict['total_time_spent'] = issue_fields.get('aggregatetimespent')
        priority = issue_fields.get('priority')
        if priority:
            issue_dict['priority'] = priority.get('name')
        resolution = issue_fields.get('resolution')
        if resolution:
            issue_dict['resolution'] = resolution.get('name')
        issue_dict['summary'] = issue_fields.get('summary')
        status = issue_fields.get('status')
        if status:
            issue_dict['status'] = status.get('name')
        issue_dict['labels'] = ';'.join(issue_fields.get('labels', ''))
        issue_dict['created_date'] = string_to_datetime(issue_fields.get('created'))
        issue_dict['resolved_date'] = string_to_datetime(issue_fields.get('resolutiondate'))
        issue_dict['last_updated_date'] = string_to_datetime(issue_fields.get('updated'))
        issue_dict['start_date'] = None
        issue_dict['components'] = ';'.join([component.get('name') for component in issue_fields.get('components',
                                                                                                     [])])
        issue_dict['subtasks'] = ';'.join([subtask.get('key') for subtask in issue_fields.get('subtasks', [])])
        issue_dict['linked_issues'] = self._get_linked_issues(issue_fields)
        fix_version = issue_fields.get('fixVersions')
        df_versions_one_item, issue_dict['fix_versions'] = self._get_latest_fix_version_for_issue(fix_version)
        return issue_dict, df_versions_one_item

    @staticmethod
    def _concat_latest_versions(df_versions: pd.DataFrame,
                                df_versions_one_item: pd.Series | pd.DataFrame) -> pd.DataFrame:
        """Concatenate the latest fix version data for one issue with the DataFrame with the all latest fix versions."""
        if not df_versions_one_item.empty:
            df_versions = pd.concat([df_versions, df_versions_one_item.to_frame().T], ignore_index=True)
        return df_versions

    @staticmethod
    def _get_linked_issues(issue_fields: dict) -> str:
        """Get concatenated string with linked issues."""
        linked_issues = None
        linked_issue = issue_fields.get('issuelinks')
        if linked_issue is not None:
            linked_issues_conc = ''
            for inward_issue in linked_issue:
                linked_issues_conc = ';'.join([linked_issues_conc,
                                               inward_issue.get('type').get(
                                                   'inward') + ' ' + inward_issue.get(
                                                   'inwardIssue').get(
                                                   'key') if inward_issue.get(
                                                   'inwardIssue') is not None else inward_issue.get(
                                                   'type').get(
                                                   'inward') + ' ' + inward_issue.get(
                                                   'outwardIssue').get(
                                                   'key')])
            linked_issues = linked_issues_conc[1:]
        return linked_issues

    @staticmethod
    def _get_latest_fix_version_for_issue(fix_version_list: list) -> \
            Union[tuple[pd.Series, str], tuple[pd.Series, None]]:
        """Get the latest release data that an issue have information on."""
        if not fix_version_list:
            return pd.Series(), None

        fix_versions_dict = defaultdict(list)
        fields = ('id', 'name',  'releaseDate', 'status')
        for field in fields:
            fix_versions_dict[field] = [version.get(field, 'None') for version in fix_version_list]
        df_versions_one_item = pd.DataFrame.from_records(fix_versions_dict)
        df_versions_one_item = df_versions_one_item.sort_values(by='releaseDate', ascending=False)
        df_versions_one_item = df_versions_one_item.iloc[0, :]
        return df_versions_one_item, ';'.join(fix_versions_dict['name'])

    @staticmethod
    def _get_custom_fields_values(issue_fields: dict, custom_fields_id: dict) -> dict:
        """Get Jira custom fields values."""
        custom_fields_values = {}
        for key, value in custom_fields_id.items():
            custom_fields_values[key] = []
            for i in range(1, len(value)):
                try:
                    custom_fields_values[key].append(issue_fields.get(value[i]))
                except IndexError:
                    custom_fields_values[key] += [None]
        for key, value in custom_fields_values.items():
            custom_fields_values[key] = None
            for field_value in value:
                if field_value:
                    custom_fields_values[key] = get_field_value(field_value)
                    break
        return custom_fields_values

    @staticmethod
    def _get_issues_changelog(issue: Issue) -> Optional[list]:
        """Get the changelog for the given issue."""
        histories = issue.raw.get('changelog', {}).get('histories')
        result = [{'field': None, 'fromString': None, 'toString': None, 'changelog_date': None}]

        if len(histories) == 0:
            return result

        for history in histories:
            for item in history['items']:
                changelog = {}
                changelog_date = string_to_datetime(history['created'])
                changelog['field'] = item['field']
                changelog['fromString'] = item['fromString']
                changelog['toString'] = item['toString']
                changelog['changelog_date'] = changelog_date
                result.append(changelog)
        return result


class JiraIssuesUpdate(JiraIssues):
    """
    A class used to update Jira issues.

    This class inherits from the JiraIssues class and provides additional methods to extract issues from Jira,
    define the request type of issue, and duplicate defects in the issues DataFrame.

    Attributes
    ----------
    projects : str
        The Jira projects to extract issues from.
    closed_issues_based_on : int
        The criteria to consider an issue as closed: 1 for status, 2 for resolved date.
    closed_status : str
        The status that indicates an issue is closed.
    defects_name : str
        The name of the issue type that is considered a defect.
    """

    def extract_issues_from_jira(self, custom_fields: dict, dates: str) -> Optional[tuple[pd.DataFrame, pd.DataFrame]]:
        """
        Extract updated after set date issues data from Jira with default and custom fields values.

        Args:
            team_field: str
                the ID of a custom field for the team
            defects_environment_field: str
                the ID of a custom field for the environment where bugs/defects were registered
            dates: str
                the date after which issues were updated
        """
        jql_query = f'project = {self.projects} AND updated >= {dates[0]}'
        fields = self._list_jira_fields(custom_fields)

        data_jira, df_versions = self._request_data_from_jira(custom_fields, fields, jql_query)
        if not data_jira.empty:
            data_jira['request_type'] = data_jira.apply(
                lambda x: self._define_request_type(x['status'], x['resolved_date']), axis=1)
            data_jira = self._duplicate_defects(data_jira, self.defects_name)
        return data_jira, df_versions

    def _define_request_type(self, status: str, resolved_date: str) -> str:
        """Define value of the request_type based on the issue status."""
        if ((self.closed_issues_based_on == 1 and status == self.closed_status)
                or (self.closed_issues_based_on == 2 and resolved_date)):
            return 'closed'
        return 'open'

    @staticmethod
    def _duplicate_defects(df_issues: pd.DataFrame, defect_type: str) -> pd.DataFrame:
        """Duplicate rows of the DataFrame if the issue type is Bug."""
        df_defects = df_issues[df_issues['issue_type'] == defect_type]
        if len(df_defects) == 0:
            return df_issues
        df_defects['request_type'] = 'defect'
        return pd.concat([df_issues, df_defects], ignore_index=True)
