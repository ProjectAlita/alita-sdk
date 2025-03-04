# transform.py

**Path:** `src/alita_sdk/community/eda/utils/transform.py`

## Data Flow

The data flow within `transform.py` revolves around transforming DataFrames that contain data extracted from Azure DevOps. The primary data element is a DataFrame (`df_runs`) that holds information about pipeline runs and jobs. The data flow can be summarized as follows:

1. **Input DataFrame (`df_runs`)**: The input is a DataFrame containing pipeline run data, including job start and finish times.
2. **Sorting and Grouping**: The DataFrame is sorted by `run_id` and `job_start_time`, and jobs are grouped by `run_id` to assign sequence numbers.
3. **Calculating Waiting Time**: For each job, the waiting time is calculated based on the job's sequence number, start time, finish time of the previous job, and run creation date.
4. **Output DataFrame**: The resulting DataFrame includes the calculated waiting times and excludes intermediate columns used for calculations.

Example:
```python
# Sorting and grouping jobs by run_id and job_start_time
    df_sorted = df_runs.sort_values(by=['run_id', 'job_start_time'], ignore_index=True)
    df_sorted['jobs_seq_num'] = df_sorted.groupby('run_id').cumcount() + 1

    df_sorted['job_finish_time_previous'] = df_sorted['job_finish_time'].shift(+1)
    df_sorted['waiting time'] = df_sorted.apply(lambda x: get_time_between(x['jobs_seq_num'],
                                                                           x['job_start_time'],
                                                                           x['job_finish_time_previous'],
                                                                           x['run_created_date']), axis=1)
```

## Functions Descriptions

### `waiting_time_for_jobs_in_pipeline(df_runs: pd.DataFrame) -> pd.DataFrame`

This function calculates the waiting time between jobs in a pipeline and adds it to the DataFrame. It sorts the DataFrame by `run_id` and `job_start_time`, assigns sequence numbers to jobs, and calculates the waiting time using the `get_time_between` function. The resulting DataFrame includes the calculated waiting times and excludes intermediate columns.

### `get_time_between(job_seq_num: int, job_start_time: str, job_finish_time_previous: str, run_created_date: str) -> float`

This function calculates the waiting time for jobs in a pipeline. It computes the time difference between the job start time and the finish time of the previous job, as well as the time difference between the job start time and the run creation date. The waiting time is determined based on the job's sequence number and the calculated time differences.

### `calculate_time_difference(next_date: str, previous_date: str) -> Optional[float]`

This function calculates the time difference between two dates in minutes. It converts the date strings to datetime objects using the `string_to_datetime` function and computes the difference in minutes. If the date conversion fails, it returns `None`.

## Dependencies Used and Their Descriptions

### `pandas`

The `pandas` library is used for DataFrame manipulation, including sorting, grouping, and applying functions to DataFrame rows.

### `string_to_datetime`

The `string_to_datetime` function from the `convert_to_datetime` module is used to convert date strings to datetime objects for time difference calculations.

## Functional Flow

1. **Input DataFrame**: The process starts with an input DataFrame containing pipeline run data.
2. **Sorting and Grouping**: The DataFrame is sorted by `run_id` and `job_start_time`, and jobs are grouped by `run_id` to assign sequence numbers.
3. **Calculating Waiting Time**: For each job, the waiting time is calculated using the `get_time_between` function, which computes time differences based on job sequence numbers and dates.
4. **Output DataFrame**: The resulting DataFrame includes the calculated waiting times and excludes intermediate columns used for calculations.

## Endpoints Used/Created

This module does not explicitly define or call any endpoints. It focuses on transforming DataFrames with data extracted from Azure DevOps.