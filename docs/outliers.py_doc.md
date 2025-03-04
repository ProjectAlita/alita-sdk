# outliers.py

**Path:** `src/alita_sdk/community/eda/utils/outliers.py`

## Data Flow

The data flow within the `outliers.py` file primarily revolves around the calculation of outliers in a given dataset. The data originates from a pandas DataFrame or Series, undergoes statistical calculations to determine the interquartile range (IQR), and results in the identification of outliers based on the calculated upper and lower bounds.

For example, in the `get_outliers_upper_bound` function, the data flow can be traced as follows:

1. **Input:** A pandas Series `s` is passed as an argument.
2. **Transformation:** The first and third quartiles (Q1 and Q3) are calculated using the `quantile` method.
3. **Calculation:** The IQR is computed as the difference between Q3 and Q1.
4. **Output:** The upper bound for outliers is determined by adding 1.5 times the IQR to Q3 and returned.

```python
import pandas as pd

def get_outliers_upper_bound(s: pd.Series) -> float:
    q1 = s.quantile(0.25)  # Calculate the first quartile
    q3 = s.quantile(0.75)  # Calculate the third quartile
    iqr = q3 - q1  # Compute the interquartile range
    upper_bound = q3 + (1.5 * iqr)  # Determine the upper bound for outliers
    return upper_bound
```

## Functions Descriptions

### `get_outliers_upper_bound`

This function calculates the upper bound for outliers in a pandas Series. It takes a single parameter:
- `s` (pd.Series): The input pandas Series for which the upper bound of outliers is to be calculated.

The function computes the first quartile (Q1) and third quartile (Q3) of the Series, calculates the IQR, and then determines the upper bound for outliers as Q3 + 1.5 * IQR. The result is returned as a float.

### `calculate_outliers`

This function identifies outliers in a specified column of a pandas DataFrame. It takes two parameters:
- `records_group` (pd.DataFrame): The input DataFrame containing the data.
- `column_name` (str): The name of the column for which outliers are to be calculated.

The function calculates Q1, Q3, and IQR for the specified column, and then creates a new column `outlier` in the DataFrame, marking rows as outliers if their values fall outside the range [Q1 - 1.5 * IQR, Q3 + 1.5 * IQR]. The modified DataFrame is returned.

```python
import pandas as pd

def calculate_outliers(records_group: pd.DataFrame, column_name: str) -> pd.DataFrame:
    q1 = records_group[column_name].quantile(0.25)  # Calculate the first quartile
    q3 = records_group[column_name].quantile(0.75)  # Calculate the third quartile
    iqr = q3 - q1  # Compute the interquartile range
    records_group['outlier'] = (
        (records_group[column_name] > (q3 + 1.5 * iqr)) |  # Mark as outlier if value is above upper bound
        (records_group[column_name] < (q1 - 1.5 * iqr))  # Mark as outlier if value is below lower bound
    )
    return records_group
```

## Dependencies Used and Their Descriptions

The `outliers.py` file relies on the following dependencies:

- `pandas`: This library is used for data manipulation and analysis. In this file, it is used to handle data in Series and DataFrame formats, and to perform statistical calculations such as quantiles and IQR.

## Functional Flow

The functional flow of the `outliers.py` file involves the following steps:

1. **Import Dependencies:** The `pandas` library is imported.
2. **Define Functions:** Two functions, `get_outliers_upper_bound` and `calculate_outliers`, are defined to perform outlier calculations.
3. **Outlier Calculation:** The functions are designed to be called with appropriate arguments (a pandas Series or DataFrame and column name) to calculate and identify outliers based on statistical methods.

The process is straightforward, with each function performing specific calculations and returning the results.

## Endpoints Used/Created

The `outliers.py` file does not define or interact with any endpoints. It is a utility module focused on data processing and outlier calculation within pandas DataFrames and Series.