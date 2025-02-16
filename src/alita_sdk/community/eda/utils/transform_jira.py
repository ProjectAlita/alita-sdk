"""Lead time distribution for closed and open issues."""

from datetime import timedelta
import pandas as pd
import numpy as np

from ..utils.convert_to_datetime import string_to_datetime
from ..utils.constants import DATE_UTC, WAITING_FOR_RELEASE_STATUS, ACTIVE_STATUSES, STATUSES_NOT_IN_CYCLE_TIME


pd.options.mode.chained_assignment = None
pd.set_option('display.precision', 2)
pd.set_option('display.max_rows', None)
pd.set_option("display.max_columns", None)


def get_field_value(field) -> str:
    """
    Extract field value from the custom field string in the issues dataframe.
    Covers only basic cases.
    """

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


def fix_columns_values(df_issues: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """
    Fix columns values in the issues dataframe.
    """
    for col in columns:
        df_issues[col] = df_issues[col].apply(get_field_value).reset_index(drop=True)

    return df_issues


def _get_subtasks(df_issues: pd.DataFrame) -> list:
    """
    Extract subtasks from the issues changelog.
    """
    if df_issues.empty:
        return []

    df_issues = df_issues.fillna('')
    subtasks = df_issues[df_issues['subtasks'] != '']['subtasks']
    subtasks = subtasks.apply(lambda x: x.split(';'))
    subtasks = subtasks.explode()

    return subtasks.to_list()


def _get_changelog_for_original_value(df_issues: pd.DataFrame, column: str, changelog: pd.DataFrame) -> pd.DataFrame:
    """
    Add to changelog values that were made on the issue creation.
    """
    # add issues that are not in changelog, but with value added at the creation
    no_changelog_issues = set(df_issues['issue_key'].unique()) - set(changelog['issue_key'].unique())
    no_changelog_issues = df_issues[
        df_issues['issue_key'].isin(no_changelog_issues) & (df_issues[column] != '')
        ].drop_duplicates(subset=['issue_key'])
    new_rows_1 = no_changelog_issues[['issue_key', 'issue_type', 'created_date', 'resolved_date', 'project_key',
                                      'project_name', 'team', 'sprint']]
    new_rows_1['changelog_date'] = new_rows_1['created_date']
    new_rows_1['fromString'] = ''
    new_rows_1['toString'] = no_changelog_issues[column]

    # add issues that are in changelog and with value at the creation
    first_change = changelog.groupby('issue_key')['changelog_date'].min().reset_index()
    new_rows_2 = pd.merge(first_change, changelog, how='left', on=['issue_key', 'changelog_date'])
    new_rows_2 = new_rows_2[new_rows_2['fromString'] != '']
    new_rows_2['toString'] = new_rows_2['fromString']
    new_rows_2['fromString'] = ''
    new_rows_2['changelog_date'] = new_rows_2['created_date']

    changelog = pd.concat([changelog, new_rows_1, new_rows_2], ignore_index=True)

    return changelog


def get_sprints_changelog(df_issues: pd.DataFrame) -> pd.DataFrame:
    """
    Extract sprints changelog from the issues changelog.
    """
    if df_issues.empty:
        return pd.DataFrame()

    df_issues = df_issues[~df_issues['issue_key'].isin(_get_subtasks(df_issues))]  # exclude subtasks
    df_issues = df_issues.fillna('')
    sprints_changelog = df_issues[df_issues['field'] == 'Sprint'][
        ['issue_key', 'issue_type', 'created_date', 'resolved_date', 'project_key',
         'project_name', 'team', 'fromString', 'toString', 'changelog_date', 'sprint']]

    sprints_changelog = _get_changelog_for_original_value(df_issues, 'sprint', sprints_changelog)

    sprints_changelog = sprints_changelog[sprints_changelog['fromString'] != sprints_changelog['toString']]
    sprints_changelog = sprints_changelog.drop_duplicates()

    sprints_changelog['fromString'] = sprints_changelog['fromString'].astype("string")
    sprints_changelog['toString'] = sprints_changelog['toString'].astype("string")

    return sprints_changelog


def get_story_points_changelog(df_issues: pd.DataFrame) -> pd.DataFrame:
    """
    Extract story points changelog from the issues changelog.
    """
    if df_issues.empty:
        return pd.DataFrame()

    df_issues = df_issues.fillna('')

    df_issues = df_issues[~df_issues['issue_key'].isin(_get_subtasks(df_issues))]  # exclude subtasks
    story_points_changelog = df_issues[df_issues['field'] == 'Story Points'][
        ['issue_key', 'issue_type', 'created_date', 'resolved_date', 'project_key',
         'project_name', 'team', 'fromString', 'toString', 'changelog_date', 'sprint']]

    story_points_changelog = _get_changelog_for_original_value(df_issues, 'story_points', story_points_changelog)

    story_points_changelog['fromString'] = story_points_changelog['fromString']\
        .replace('', np.nan).astype("float").fillna(0)
    story_points_changelog['toString'] = story_points_changelog['toString']\
        .replace('', np.nan).astype("float").fillna(0)
    story_points_changelog = story_points_changelog.drop_duplicates().fillna('')

    return story_points_changelog


def _calculate_sprint_changes(sprints_changelog: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate rows for each sprint change and identify sprint change type (removed or added)
    """
    sprints_changelog['fromString'] = sprints_changelog['fromString'].apply(lambda x: list(filter(None, x.split(', '))))
    sprints_changelog['toString'] = sprints_changelog['toString'].apply(lambda x: list(filter(None, x.split(', '))))
    sprints_changelog['sprint_changed'] = [
        list(set(row[0]).symmetric_difference(set(row[1]))) for row in
        zip(sprints_changelog['fromString'], sprints_changelog['toString'])]
    sprints_changelog = sprints_changelog.explode('sprint_changed')
    sprints_changelog['change_type'] = [
        'added' if row[0] in row[1] else 'removed' for row in
        zip(sprints_changelog['sprint_changed'], sprints_changelog['toString'])]
    sprints_changelog.drop(columns=['fromString', 'toString'], inplace=True)

    return sprints_changelog


def _merge_sprint_and_changelog(
        df_sprints: pd.DataFrame, sprints_changelog: pd.DataFrame, buffer_time: timedelta) -> pd.DataFrame:
    """
    Calculate sprint start and end dates and merge sprint data with sprint changelog.
    """
    sprints_changelog = pd.merge(
        sprints_changelog, df_sprints[['completeDate', 'activatedDate', 'name']],
        how='inner', left_on='sprint_changed', right_on='name').reset_index(drop=True)
    sprints_changelog = sprints_changelog.rename(columns={
        'completeDate': 'sprint_end', 'activatedDate': 'sprint_start'})

    # select last change before the sprint start
    sprints_changelog_before_sprint = sprints_changelog[
        sprints_changelog['changelog_date'] <= sprints_changelog['sprint_start'] + buffer_time]\
        .sort_values(by='changelog_date').groupby(['issue_key', 'name']).last().reset_index()
    sprints_changelog = pd.concat([
        sprints_changelog[sprints_changelog['changelog_date'] > sprints_changelog['sprint_start'] + buffer_time],
        sprints_changelog_before_sprint])

    return sprints_changelog


def _calculate_sprints_issues(issues_group: pd.Series, buffer_time: timedelta = timedelta(0)) -> pd.Series:
    """
    Calculate the number of issues in a sprint, which were committed, completed, and added during the sprint.
    """
    issues_group = issues_group.reset_index().fillna('')
    issues_group['was_in_sprint'] = [row[0] in row[1] for row in
                                     zip(issues_group['sprint_changed'], issues_group['sprint'])]
    sprints_issues = pd.Series({
        'committed_issues':
        len(issues_group[
            (issues_group['change_type'] == 'added') &
            (issues_group['changelog_date'] <= issues_group['sprint_start'] + buffer_time)]
            ['issue_key'].unique()),
        'completed_issues': len(issues_group[
            (issues_group['was_in_sprint']) &
            (issues_group['resolved_date'] >= issues_group['sprint_start']) &
            (issues_group['resolved_date'] <= issues_group['sprint_end'])]
            ['issue_key'].unique()),
        'added_issues': len(issues_group[
            (issues_group['change_type'] == 'added') &
            (issues_group['changelog_date'] > issues_group['sprint_start'] + buffer_time)]
            ['issue_key'].unique()),
        'removed_issues': len(issues_group[
            (issues_group['change_type'] == 'removed') &
            (issues_group['changelog_date'] > issues_group['sprint_start'] + buffer_time)]
            ['issue_key'].unique())
    })
    sprints_issues['issues_count'] = sprints_issues['committed_issues'] + sprints_issues['added_issues']
    return sprints_issues


def _calculate_sprints_story_points(issues_group: pd.Series, buffer_time: timedelta = timedelta(0)) -> pd.Series:
    issues_group = issues_group.reset_index().fillna('')
    issues_group['was_in_sprint'] = [row[0] in row[1] for row in
                                     zip(issues_group['sprint_changed'], issues_group['sprint'])]
    return pd.Series({
        'committed_story_points':
        issues_group[
            (issues_group['change_type'] == 'added') &
            (issues_group['sprint_changelog_date'] <= issues_group['sprint_start'] + buffer_time) &
            (issues_group['changelog_date'] <= issues_group['sprint_start'] + buffer_time)]
            .sort_values('changelog_date').groupby(['issue_key']).last()['toString'].sum(),
        'completed_story_points':
        issues_group[
            (issues_group['was_in_sprint']) &
            (issues_group['resolved_date'] > issues_group['sprint_start']) &
            (issues_group['resolved_date'] <= issues_group['sprint_end'])]
            .sort_values('changelog_date').groupby(['issue_key']).last()['toString'].sum(),
        'added_story_points':
        issues_group[
            (issues_group['changelog_date'] > issues_group['sprint_start'] + buffer_time) &
            (issues_group['changelog_date'] < issues_group['sprint_end']) &
            (issues_group['changelog_date'] > issues_group['sprint_changelog_date']) &
            (issues_group['toString'] > issues_group['fromString'])]
            .eval('toString - fromString').sum() +
        issues_group[
            (issues_group['change_type'] == 'added') &
            (issues_group['sprint_changelog_date'] > issues_group['sprint_start'] + buffer_time) &
            (issues_group['changelog_date'] < issues_group['sprint_changelog_date'])]
            .sort_values('changelog_date').groupby(['issue_key']).last()['toString'].sum(),
        'removed_story_points':
        issues_group[
            (issues_group['changelog_date'] > issues_group['sprint_start'] + buffer_time) &
            (issues_group['changelog_date'] < issues_group['sprint_end']) &
            (issues_group['changelog_date'] > issues_group['sprint_changelog_date']) &
            (issues_group['fromString'] > issues_group['toString'])]
            .eval('fromString - toString').sum() +
        issues_group[
            (issues_group['change_type'] == 'removed') &
            (issues_group['sprint_changelog_date'] > issues_group['sprint_start'] + buffer_time) &
            (issues_group['changelog_date'] < issues_group['sprint_changelog_date'])]
            .sort_values('changelog_date').groupby(['issue_key']).last()['toString'].sum()
    })


def calculate_sprint_metrics(
        df_issues: pd.DataFrame, df_sprints: pd.DataFrame,
        buffer_time: timedelta = timedelta(0)) -> pd.DataFrame:
    """
    Calculate metrics for sprints based on the issues sprint changelog and sprints data.
    """
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


def lead_time_distribution_jira(df_issues: pd.DataFrame) -> pd.DataFrame:
    """
    Take the Jira output data frame with issues, transform it and calculates time each issue spend in each status.
    """
    # Leave only needed columns in the initial dataframe. Filter out defects (as they are in open and
    #  closed issues also) and changelog not related to statuses' change
    if df_issues.empty:
        return pd.DataFrame()
    df_filtered = df_issues[['issue_key', 'issue_type',  'created_date', 'fromString', 'toString', 'changelog_date',
                             'status', 'team', 'project_key', 'request_type']][
        (df_issues['request_type'] != 'defect') & ((df_issues['field'] == 'status') | (df_issues['field'].isnull()))]
    if df_filtered.empty:
        return pd.DataFrame()

    # copy current status to the field from_string for all issues
    # (from_string doesn't contain the last status of issue)
    df_filtered['fromString'] = np.where((df_filtered.fromString.isna()), df_filtered.status, df_filtered.fromString)

    # Sort by changelog date to have statuses chronologically ordered
    df_filtered = df_filtered.sort_values(by=['issue_key', 'changelog_date'], na_position='last')

    # Add count and running count of rows for every issue to know statuses sequence
    # number and their total count for every issue
    df_filtered['cum_count'] = df_filtered.groupby(['issue_key']).cumcount()
    df_filtered['count'] = df_filtered.groupby(['issue_key'])['issue_key'].transform('count')

    # Changelog_date is a date when an issue moved from one status to another. Shift Changelog_date one row down to have
    # this date in front of a status name in the column from_string as start date and rename it to from_date
    df_filtered = df_filtered.reset_index(drop=True)
    df_dates_shifted = df_filtered.reset_index()[['index', 'changelog_date']]
    df_dates_shifted['index_new'] = df_dates_shifted['index'] + 1
    df_dates_shifted = df_dates_shifted.drop(columns=['index'])
    df_dates_shifted = df_dates_shifted.rename(columns={'changelog_date': 'from_date'})
    df_filtered = df_filtered.merge(df_dates_shifted, how='left', left_index=True, right_on='index_new')

    # The starting date for the first status of an issue is their creation date
    df_filtered['from_date'] = np.where((df_filtered.cum_count == 0), df_filtered.created_date, df_filtered.from_date)
    # For open issues the end date of the last status is a current date
    df_filtered.loc[
        (df_filtered.changelog_date.isna()) & (df_filtered.request_type == 'open'), 'changelog_date'] = DATE_UTC
    # Calculate time in status for every issue
    df_filtered['time_in_status'] = df_filtered.apply(get_days_between, args=('from_date', 'changelog_date'), axis=1)
    # Remove extra columns from resulted dataframe
    df_filtered = df_filtered[
        ['issue_key', 'issue_type', 'request_type', 'fromString',
         'from_date', 'changelog_date', 'time_in_status', 'cum_count']
    ]
    df_filtered = df_filtered.rename(columns={'fromString': 'status_history', 'changelog_date': 'to_date'})
    return df_filtered


def statuses_order_jira(df_issues: pd.DataFrame) -> pd.DataFrame:
    """
    Takes transformed data frame by the function lead_time_distribution_jira with issues changelog and returns
    a dataframe with statuses indexes and count of every historical status for every issue.
    """
    if df_issues.empty:
        return pd.DataFrame()
    df_map = df_issues.groupby(['status_history', 'cum_count']).size().reset_index(name='occurrences')
    df_map = df_map.sort_values(
        by=['status_history', 'occurrences'], ascending=False).drop_duplicates(subset=['status_history'])
    df_map = df_map.sort_values(by=['cum_count', 'occurrences'], ascending=[True, False]).reset_index(drop=True)
    df_map = df_map.reset_index()
    df_map = df_map.rename(columns={'index': 'status_raw_index'})
    df_map['status_mapped_index'] = df_map['status_raw_index']
    df_map['status_mapped'] = df_map['status_history']
    df_map = df_map.rename(columns={'status_history': 'status_raw'})
    df_map['status_type'] = df_map['status_raw'].apply(
        lambda x: 'Active' if x.lower() in ACTIVE_STATUSES else 'Waiting')
    df_map['add_to_cycle_time'] = df_map['status_raw'].apply(
        lambda x: 'y' if not x.lower() in STATUSES_NOT_IN_CYCLE_TIME else 'n')
    df_map = df_map[[
        'status_raw',
        'status_raw_index',
        'status_mapped',
        'status_mapped_index',
        'status_type',
        'add_to_cycle_time',
    ]]
    return df_map


def merge_issues_and_history(data_jira_fin: pd.DataFrame, time_in_status_df: pd.DataFrame) -> pd.DataFrame:
    """Merge issues data without duplicates with transformed statuses' history."""
    if data_jira_fin.empty:
        return pd.DataFrame()
    data_jira_fin = data_jira_fin.drop_duplicates(subset=['issue_key', 'request_type'])
    data_jira_fin = data_jira_fin.drop(
        columns=['field', 'fromString', 'toString', 'changelog_date'])
    if time_in_status_df.empty:
        data_jira_with_history = data_jira_fin
        data_jira_with_history[['status_history', 'time_in_status']] = None
        return data_jira_with_history

    time_in_status_df_ = time_in_status_df.drop(columns=['issue_type', 'cum_count', 'request_type'])
    data_jira_with_history = pd.merge(data_jira_fin, time_in_status_df_, how='left', on='issue_key')

    return data_jira_with_history


def copy_to_resolution_date(
        time_in_status_df: pd.DataFrame, data_jira: pd.DataFrame, closed_status: str) -> pd.DataFrame:
    """
    Copy the last status change date to the field 'resolved_date' for JQL request for closed issues,
    which is build based on the issues' field 'status'.
    """
    df_max_latest_status_transition = time_in_status_df.sort_values(by=['issue_key', 'from_date'], ascending=False)
    df_max_latest_status_transition = df_max_latest_status_transition.drop_duplicates(subset=['issue_key'],
                                                                                      keep='first')
    data_jira = data_jira.merge(
        df_max_latest_status_transition, how='left', on='issue_key', suffixes=('', '_joined'))
    data_jira['resolved_date'] = pd.to_datetime(data_jira['resolved_date'])
    data_jira.loc[(data_jira['status'] == closed_status), 'resolved_date'] = data_jira['from_date_joined']
    data_jira = data_jira.drop(columns=['issue_type_joined', 'request_type_joined', 'status_history_joined',
                                        'from_date_joined', 'to_date_joined', 'time_in_status_joined', 'cum_count'])
    return data_jira


def map_release_as_status(df_issues: pd.DataFrame, df_map: pd.DataFrame) -> pd.DataFrame:
    """Add waiting for release to the statuses' mapping after Jira issues data has been extracted."""
    if df_map.empty:
        return df_map
    waiting_for_release_index = df_map['status_raw_index'].max() + 1
    df_release_as_status = pd.DataFrame.from_dict({
        'status_raw': [WAITING_FOR_RELEASE_STATUS],
        'status_raw_index': [waiting_for_release_index],
        'status_mapped': [WAITING_FOR_RELEASE_STATUS],
        'status_mapped_index': [waiting_for_release_index],
        'status_type': ['Waiting'],
        'add_to_cycle_time': 'n',
    })
    if WAITING_FOR_RELEASE_STATUS in df_issues['status_history'].unique():
        df_map = pd.concat([df_map, df_release_as_status], ignore_index=True)
    return df_map.sort_values(by=['status_raw_index']).reset_index(drop=True)


def define_index_for_release(df_map: pd.DataFrame) -> str:
    """Define index for the pseudo-status 'Waiting for release' as the maximum statuses index plus one."""
    df_map = df_map.sort_values(by='status_raw_index', ascending=False, ignore_index=True)
    return df_map.at[0, 'status_raw_index']


def add_releases_info(data_jira_final: pd.DataFrame, df_versions: pd.DataFrame) -> pd.DataFrame:
    """
    Add to the issues' data, which have calculated time every issue spends in every status, waiting time for the
    latest release. The column 'status_history' is populated with pseudo-status 'Waiting for release'.
    """
    data_jira = data_jira_final[data_jira_final['request_type'] == 'closed']

    if df_versions.empty or data_jira.empty:
        return data_jira_final

    data_jira = data_jira.drop_duplicates(subset=['issue_key', 'request_type'])
    data_jira = data_jira.drop(columns=['status_history', 'from_date', 'to_date', 'time_in_status'])
    df_versions = transform_versions_data(df_versions)
    data_jira = merge_jira_and_versions_data(data_jira, df_versions)
    data_jira_with_releases = pd.concat([data_jira_final, data_jira], axis=0)
    data_jira_with_releases = data_jira_with_releases.sort_values(by='issue_key', ignore_index=True)
    return data_jira_with_releases


def merge_jira_and_versions_data(data_jira: pd.DataFrame, data_versions) -> pd.DataFrame:
    """
    Merge issues data with versions, calculate time between issues resolution date and related fix versions release
    dates, drop columns, copy data from the column resolved_date to the from_date.
    """
    data_jira = data_jira.merge(data_versions, left_on='issue_key', right_on='version_issue_key', how='inner')
    if data_jira.empty:
        return pd.DataFrame()
    data_jira['time_in_status'] = data_jira.apply(get_days_between, args=('resolved_date', 'to_date'), axis=1)
    data_jira = data_jira.drop(columns=['version_issue_key', 'version_id', 'version_name', 'version_releaseDate',
                                        'version_status'])
    data_jira['from_date'] = data_jira['resolved_date']
    return data_jira


def transform_versions_data(df_versions: pd.DataFrame) -> pd.DataFrame:
    """
    Filter dataframe with fix versions data, add prefix version_ to the columns' names, add new column with
    'Waiting for release' values, convert string values version_releaseDate to the datetime format.
    """
    df_versions = df_versions[~df_versions['releaseDate'].isna()]
    df_versions.columns = df_versions.columns.map(lambda x: f'version_{x}')
    df_versions['status_history'] = WAITING_FOR_RELEASE_STATUS
    df_versions['to_date'] = df_versions['version_releaseDate'].apply(string_to_datetime)
    return df_versions


def get_days_between(row: pd.Series, start_date: str, end_date: str) -> float:
    """Finds number of days between dates in a dataframe row."""
    if all([row[end_date], row[start_date]]):
        return (row[end_date] - row[start_date]).total_seconds() / 60 / 60 / 24
    return None
