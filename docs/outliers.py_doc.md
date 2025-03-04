# outliers.py

**Path:** `src/alita_sdk/community/eda/utils/outliers.py`

## Data Flow

The data flow within the `outliers.py` file is centered around the calculation of outliers in a pandas DataFrame or Series. The data originates from a pandas Series or DataFrame column, undergoes quantile calculations to determine the interquartile range (IQR), and is then used to identify outliers based on the IQR. The data is transformed by calculating the first quartile (Q1), third quartile (Q3), and IQR, and then determining the upper bound for outliers. The final destination of the data is either a float value representing the upper bound of outliers or a DataFrame with an additional column indicating outlier status.

Example:
```python
import pandas as pd

def get_outliers_upper_bound(s: pd.Series) -> float:
    q1 = s.quantile(0.25)  # Calculate the first quartile
    q3 = s.quantile(0.75)  # Calculate the third quartile
    iqr = q3 - q1  # Calculate the interquartile range
    upper_bound = q3 + (1.5 * iqr)  # Determine the upper bound for outliers
    return upper_bound
```
In this example, the data flow involves calculating the quantiles and IQR to determine the upper bound for outliers.

## Functions Descriptions

### get_outliers_upper_bound

This function calculates the upper bound for outliers in a pandas Series. It takes a pandas Series as input and returns a float representing the upper bound for outliers. The function calculates the first quartile (Q1) and third quartile (Q3) of the Series, computes the interquartile range (IQR), and then determines the upper bound by adding 1.5 times the IQR to Q3.

Example:
```python
def get_outliers_upper_bound(s: pd.Series) -> float:
    q1 = s.quantile(0.25)  # Calculate the first quartile
    q3 = s.quantile(0.75)  # Calculate the third quartile
    iqr = q3 - q1  # Calculate the interquartile range
    upper_bound = q3 + (1.5 * iqr)  # Determine the upper bound for outliers
    return upper_bound
```

### calculate_outliers

This function identifies outliers in a specified column of a pandas DataFrame. It takes a DataFrame and a column name as input and returns the DataFrame with an additional column indicating whether each value is an outlier. The function calculates the first quartile (Q1) and third quartile (Q3) of the specified column, computes the interquartile range (IQR), and then identifies outliers as values that are either greater than Q3 + 1.5 * IQR or less than Q1 - 1.5 * IQR.

Example:
```python
def calculate_outliers(records_group: pd.DataFrame, column_name: str) -> pd.DataFrame:
    q1 = records_group[column_name].quantile(0.25)  # Calculate the first quartile
    q3 = records_group[column_name].quantile(0.75)  # Calculate the third quartile
    iqr = q3 - q1  # Calculate the interquartile range
    records_group['outlier'] = (
        (records_group[column_name] > (q3 + 1.5 * iqr)) |  # Identify values greater than the upper bound
        (records_group[column_name] < (q1 - 1.5 * iqr)))  # Identify values less than the lower bound
    return records_group
```

## Dependencies Used and Their Descriptions

The `outliers.py` file relies on the `pandas` library for data manipulation and analysis. The `pandas` library is used to handle data in Series and DataFrame formats, perform quantile calculations, and add new columns to DataFrames. The specific functions used from the `pandas` library include `pd.Series` and `pd.DataFrame` for data structures, and the `quantile` method for calculating quantiles.

Example:
```python
import pandas as pd
```
In this example, the `pandas` library is imported to enable the use of its data structures and methods for data manipulation.

## Functional Flow

The functional flow of the `outliers.py` file involves the following steps:
1. Import the `pandas` library.
2. Define the `get_outliers_upper_bound` function to calculate the upper bound for outliers in a pandas Series.
3. Define the `calculate_outliers` function to identify outliers in a specified column of a pandas DataFrame.
4. Use the `get_outliers_upper_bound` function to determine the upper bound for outliers in a Series.
5. Use the `calculate_outliers` function to add an outlier column to a DataFrame based on the specified column.

Example:
```python
import pandas as pd

def get_outliers_upper_bound(s: pd.Series) -> float:
    q1 = s.quantile(0.25)
    q3 = s.quantile(0.75)
    iqr = q3 - q1
    upper_bound = q3 + (1.5 * iqr)
    return upper_bound


def calculate_outliers(records_group: pd.DataFrame, column_name: str) -> pd.DataFrame:
    q1 = records_group[column_name].quantile(0.25)
    q3 = records_group[column_name].quantile(0.75)
    iqr = q3 - q1
    records_group['outlier'] = (
        (records_group[column_name] > (q3 + 1.5 * iqr)) |
        (records_group[column_name] < (q1 - 1.5 * iqr)))
    return records_group
```

## Endpoints Used/Created

The `outliers.py` file does not explicitly define or call any endpoints. It focuses on data manipulation and outlier calculation using the `pandas` library.