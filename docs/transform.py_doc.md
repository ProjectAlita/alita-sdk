# transform.py

**Path:** `src/alita_sdk/community/eda/utils/transform.py`

## Data Flow

The data flow within the `transform.py` file primarily revolves around the transformation of DataFrames containing data extracted from Azure DevOps. The data originates from a DataFrame passed as an argument to the functions within the file. This DataFrame is then manipulated and transformed through various operations, such as sorting, grouping, and applying custom functions to calculate new columns. The final transformed DataFrame is returned as the output.

For example, in the `waiting_time_for_jobs_in_pipeline` function, the input DataFrame `df_runs` is sorted by `run_id` and `job_start_time`, and new columns are added to calculate the waiting time between jobs in a pipeline. The data flow can be visualized as follows:

```python
# Sorting the DataFrame by run_id and job_start_time
df_sorted = df_runs.sort_values(by=['run_id', 'job_start_time'], ignore_index=True)

# Adding a new column for job sequence number
df_sorted['jobs_seq_num'] = df_sorted.groupby('run_id').cumcount() + 1

# Shifting the job_finish_time column to calculate waiting time
df_sorted['job_finish_time_previous'] = df_sorted['job_finish_time'].shift(+1)

# Applying a custom function to calculate waiting time
# The get_time_between function is called for each row in the DataFrame
# The calculated waiting time is stored in a new column 'waiting time'
df_sorted['waiting time'] = df_sorted.apply(lambda x: get_time_between(x['jobs_seq_num'],
                                                                       x['job_start_time'],
                                                                       x['job_finish_time_previous'],
                                                                       x['run_created_date']), axis=1)

# Dropping intermediate columns that are no longer needed
return df_sorted.drop(columns=['job_finish_time_previous', 'jobs_seq_num'])
```

## Functions Descriptions

### `waiting_time_for_jobs_in_pipeline`

This function calculates the waiting time between jobs in a pipeline and adds it to the input DataFrame. It takes a single parameter `df_runs`, which is a DataFrame containing information about pipeline runs and jobs. The function sorts the DataFrame by `run_id` and `job_start_time`, adds a sequence number for each job, and calculates the waiting time between jobs using the `get_time_between` function. The final DataFrame with the calculated waiting times is returned.

### `get_time_between`

This function calculates the waiting time between two jobs in a pipeline. It takes four parameters: `job_seq_num` (the sequence number of the job), `job_start_time` (the start time of the current job), `job_finish_time_previous` (the finish time of the previous job), and `run_created_date` (the creation date of the pipeline run). The function calculates the time difference between the job start time and the previous job finish time, as well as the time difference between the job start time and the run creation date. Based on the job sequence number, it determines the appropriate waiting time and returns it.

### `calculate_time_difference`

This function calculates the time difference between two dates in minutes. It takes two parameters: `next_date` and `previous_date`, both of which are strings representing dates. The function converts these strings to datetime objects using the `string_to_datetime` function and calculates the difference in minutes. If the conversion fails, it returns `None`.

## Dependencies Used and Their Descriptions

### `pandas`

The `pandas` library is used for data manipulation and analysis. It provides the DataFrame structure and various functions for sorting, grouping, and applying custom functions to the data.

### `string_to_datetime`

The `string_to_datetime` function is imported from the `convert_to_datetime` module. It is used to convert date strings to datetime objects for calculating time differences.

## Functional Flow

The functional flow of the `transform.py` file begins with the `waiting_time_for_jobs_in_pipeline` function, which is the main function responsible for transforming the input DataFrame. This function sorts the DataFrame, adds sequence numbers, and calculates waiting times using the `get_time_between` function. The `get_time_between` function, in turn, calls the `calculate_time_difference` function to compute the time differences between dates. The overall process involves sorting, grouping, and applying custom functions to the data, resulting in a transformed DataFrame with calculated waiting times.

## Endpoints Used/Created

There are no explicit endpoints used or created within the `transform.py` file. The file focuses on transforming DataFrames and does not interact with external APIs or services.
