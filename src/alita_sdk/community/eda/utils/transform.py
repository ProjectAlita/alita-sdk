"""This module transforms DataFrames with data extracted from Azure DevOps."""

from typing import Optional

import pandas as pd

from ..utils.convert_to_datetime import string_to_datetime


def waiting_time_for_jobs_in_pipeline(df_runs: pd.DataFrame) -> pd.DataFrame:
    """Add calculated waiting time between  jobs in pipelines to a Data Frame."""
    df_sorted = df_runs.sort_values(by=['run_id', 'job_start_time'], ignore_index=True)
    df_sorted['jobs_seq_num'] = df_sorted.groupby('run_id').cumcount() + 1

    df_sorted['job_finish_time_previous'] = df_sorted['job_finish_time'].shift(+1)
    df_sorted['waiting time'] = df_sorted.apply(lambda x: get_time_between(x['jobs_seq_num'],
                                                                           x['job_start_time'],
                                                                           x['job_finish_time_previous'],
                                                                           x['run_created_date']), axis=1)
    return df_sorted.drop(columns=['job_finish_time_previous', 'jobs_seq_num'])


def get_time_between(job_seq_num: int, job_start_time: str, job_finish_time_previous: str,
                     run_created_date: str) -> float:
    """Calculate waiting time for jobs in pipelines."""
    time_diff_start_finish = calculate_time_difference(job_start_time, job_finish_time_previous)
    time_diff_created_start = calculate_time_difference(job_start_time, run_created_date)
    if job_seq_num == 1:
        # For the first job in a pipeline run the waiting time is the time between the run creation and the job start
        waiting_time = time_diff_created_start
    else:
        # For the rest of the jobs in a pipeline run the waiting time is the time between the previous job finish
        waiting_time = time_diff_start_finish

    # In case some job starts before the previous job finishes, the waiting time is the time between the run creation
    # and the job start
    if waiting_time is None or waiting_time < 0:
        return time_diff_created_start

    return waiting_time


def calculate_time_difference(next_date: str, previous_date: str) -> Optional[float]:
    """Calculate the time difference between two dates in minutes."""
    try:
        return round((string_to_datetime(next_date) - string_to_datetime(previous_date)).total_seconds() / 60, 2)
    except TypeError:
        return None
