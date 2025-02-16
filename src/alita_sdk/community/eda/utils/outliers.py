"""This module contains functions to calculate outliers."""
import pandas as pd


def get_outliers_upper_bound(s: pd.Series) -> float:
    """Returns the upper bound of the outliers of a pandas series"""
    q1 = s.quantile(0.25)
    q3 = s.quantile(0.75)
    iqr = q3 - q1
    upper_bound = q3 + (1.5 * iqr)
    return upper_bound


def calculate_outliers(records_group: pd.DataFrame, column_name: str) -> pd.DataFrame:
    """Calculates outliers on column with upper bound for a group of records."""
    q1 = records_group[column_name].quantile(0.25)
    q3 = records_group[column_name].quantile(0.75)
    iqr = q3 - q1
    records_group['outlier'] = (
        (records_group[column_name] > (q3 + 1.5 * iqr)) |
        (records_group[column_name] < (q1 - 1.5 * iqr)))

    return records_group
