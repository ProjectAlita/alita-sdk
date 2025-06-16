from typing import List, Optional
import pandas as pd
from ..dataframe.utils import send_thinking_step

def set_of_column_values(df: pd.DataFrame, column_name: str) -> List[str]:
    """Unique set of values from column with list elements
    Args:
        df (pd.DataFrame): DataFrame to operate on
        column_name (str): "Column name"
        
    Returns:
        List[str]: List of unique values from the column
    """
    values = set()
    for x in df[column_name]:
        if type(x) == list:
            for y in x:
                values.add(y if type(y) == str else str(y))
        else:
            values.add(x if type(x) == str else str(x))
    send_thinking_step(func="set_of_column_values", content=f"#### Unique values for column {column_name}:\n\n{', '.join(list(values))}")
    return list(values)


def calculate_skewness_and_kurtosis(df: pd.DataFrame, columns: List[str], group_by: Optional[List[str]]=None) -> tuple:
    """Calculate skewness and kurtosis for a colum or list of columns, if group_by is provided, calculate the statistics per group.
    Args:
        df (pd.DataFrame): DataFrame to operate on
        columns (List[str]): list of columns to calculate statistics for
        group_by (Optional[List[str]], optional): list of columns to group by, defaults to None.
        
    Returns:
        tuple: (skewness_dict, kurtosis_dict) - Dictionaries containing skewness and kurtosis values
    """
    result = f"#### Calculated skewness and kurtosis\n\n" + f"**Columns**: {', '.join(columns)}\n\n"
    if group_by is None or not group_by:
        result += f"**Skewness**: {df[columns].skew().to_string()} \n\n**Kurtosis**: {df[columns].kurt().to_string()}"
    else:
        result += f"**Grouped by**: {', '.join(group_by)}\n\n"
        result += f"**Skewness**: {df.groupby(group_by)[columns].skew().to_string()} \n\n**Kurtosis**: {df.groupby(group_by)[columns].kurt().to_string()}"
    send_thinking_step(func="calculate_skewness_and_kurtosis", content=result)
    return df[columns].skew().to_dict(), df[columns].kurt().to_dict()

def calculate_mode(df: pd.DataFrame, columns: List[str], group_by: Optional[List[str]]=None) -> pd.DataFrame:
    """Calculate mode for a colum or list of columns, if group_by is provided, calculate the statistics per group
    Args:
        df (pd.DataFrame): DataFrame to operate on
        columns (List[str]): list of columns to calculate mode for
        group_by (Optional[List[str]], optional): list of columns to group by, defaults to None.
        
    Returns:
        pd.DataFrame: DataFrame containing mode values for each column
    """
    res = {}
    message = f"#### Calculated mode for columns {', '.join(columns)}:\n\n"
    if group_by is None or not group_by:
        for column in columns:
            res[column] = df[column].mode()[0]
        result = pd.DataFrame(res, index=[0])
        message += result.to_markdown()
    else:
        for column in columns:
            mode = df.groupby(group_by)[column].apply(lambda x: x.mode().iloc[0])
            res[column] = mode
        result = pd.DataFrame(res)
        message = f"Groupped by {', '.join(group_by)}\n\n{result.to_markdown()}" 
    
    send_thinking_step(func="calculate_mode", content=message)
    return result

def calculate_range(df: pd.DataFrame, columns: List[str], group_by: Optional[List[str]]=None) -> pd.Series:
    """Calculate the range for a colum or list of columns, if group_by is provided, calculate the range for each group.
    Args:
        df (pd.DataFrame): DataFrame to operate on
        columns (List[str]): list of columns to calculate range for
        group_by (Optional[List[str]], optional): list of columns to group by, defaults to None.
        
    Returns:
        pd.Series or pd.DataFrame: Series or DataFrame containing range values for each column
    """
    message = f"#### Calculated range for columns {', '.join(columns)}:\n\n"
    if group_by is None:
        result = df[columns].apply(lambda x: x.max() - x.min())
        message += result.to_markdown()
    else:
        result = df.groupby(group_by)[columns].apply(lambda x: x.max() - x.min())
        message = f"Groupped by {', '.join(group_by)}\n\n{result.to_markdown()}"
    
    send_thinking_step(func="calculate_range", content=message)
    return result

def calculate_variance(df: pd.DataFrame, columns: List[str], group_by: Optional[List[str]]=None) -> pd.Series:
    """Calculate the variance for a colum or list of columns, if group_by is provided, calculate the variance for each group.
    Args:
        df (pd.DataFrame): DataFrame to operate on
        columns (List[str]): list of columns to calculate variance for
        group_by (Optional[List[str]], optional): list of columns to group by, defaults to None.
        
    Returns:
        pd.Series or pd.DataFrame: Series or DataFrame containing variance values for each column
    """
    message = f"#### Calculated variance for columns {', '.join(columns)}:\n\n"
    if group_by is None:
        result = df[columns].var()
        message += str(result)
    else:
        result = df.groupby(group_by)[columns].var()
        message = f"Groupped by {', '.join(group_by)}\n\n{result.to_markdown()}"
    
    send_thinking_step(func="calculate_variance", content=message)
    return result
    
def pairwise_correlation(df: pd.DataFrame, columns_for_df1: List[str], columns_for_df2: List[str], method: Optional[str]="pearson") -> pd.Series:
    """ Pairwise correlation between one set of columns and another set of columns.
    Args:
        df (pd.DataFrame): DataFrame to operate on
        columns_for_df1 (List[str]): Master list of columns to be correlated against
        columns_for_df2 (List[str]): Columns to be correlated by
        method (str, optional): "Correlation method, allowed methods pearson, kendall, spearman , default is pearson"
        
    Returns:
        pd.Series: Series containing correlation values between the two sets of columns
    """
    df1 = df[columns_for_df1]
    df2 = df[columns_for_df2]
    result = df1.corrwith(df2, method=method)
    message = f"#### Pairwise correlation between {', '.join(columns_for_df1)} and {', '.join(columns_for_df2)}\n\n"
    message += result.to_markdown()
    
    send_thinking_step(func="pairwise_correlation", content=message)
    return result

def explode(df: pd.DataFrame, column_name: str) -> str:
    """Transform each element of a list-like to a row, replicating index values.
    Args:
        df (pd.DataFrame): DataFrame to operate on
        column_name (str): "Column name"
        
    Returns:
        str: Confirmation message that the column was exploded
    """
    try:
        df = df.explode(column_name)
        send_thinking_step(func="explode", content=f"#### Exploded column {column_name}")
        return "Exploded column " + column_name
    except KeyError as e:
        raise KeyError(f"Column {column_name} not found in DataFrame") from e

def delimitred_column_values_to_list(df: pd.DataFrame, column_name:str, list_column_name: str, delimiter=";") -> str:
    """Convert delimiter separated string column values to list colum values, delimeters can be comma, semicolon, space, etc. make sure you use the right one
    Args:
        df (pd.DataFrame): DataFrame to operate on
        column_name (str): "Column name"
        list_column_name (str): Name for the new column that will contain the list values
        delimiter (str, optional): "Delimiter of values in column". Defaults to ";".
        
    Returns:
        str: The name of the new column created
    """
    # Create empty column first if it doesn't exist
    if list_column_name not in df.columns:
        df[list_column_name] = None
    
    # Process each row using the actual DataFrame index
    for idx, row in df.iterrows():
        value = row[column_name]
        new_col = []
        if pd.isna(value) or value == "":
            new_col = []
        elif isinstance(value, str) and delimiter in value:
            for val in value.split(delimiter):
                if val.strip():
                    new_col.append(val.strip())
        else:
            new_col.append(str(value))
        
        # Use the actual index to set the value
        df.at[idx, list_column_name] = new_col
    result = f"Added new column {list_column_name} as a list of values from {column_name} column"
    values_set = set_of_column_values(df, list_column_name)
    result += f". Here is set of values: " + str(values_set)
    send_thinking_step(func="delimitred_column_values_to_list", content=result)
    return list_column_name

def covariance(df: pd.DataFrame, columns: Optional[List[str]]=None) -> pd.DataFrame:
    """Calculate covariance for dataset or subset of selected columns
    Args:
        df (pd.DataFrame): DataFrame to operate on
        columns (List[str], optional): list of columns to calculate covariance for, if not provided, all columns will be used. Defaults to None.
        
    Returns:
        pd.DataFrame: DataFrame containing covariance values
    """
    if columns:
        result = df[columns].cov()
        message = f"#### Calculated covariance for columns {', '.join(columns)}:\n\n{result.to_markdown()}"
        
    else:
        result = df.cov()
        message = f"#### Calculated covariance for all columns:\n\n{result.to_markdown()}"
    
    send_thinking_step(func="covariance", content=message)
    return result

def correlation(df: pd.DataFrame, column_names: List[str], method: Optional[str]="pearson") -> pd.DataFrame:
    """ Correlate data by columns - quantifies the degree to which variables are related
    Args:
        df (pd.DataFrame): DataFrame to operate on
        column_names (List[str]): List of columns to correlate
        method (str, optional): "Correlation method, allowed methods pearson, kendall, spearman , default is pearson"
        
    Returns:
        pd.DataFrame: DataFrame containing correlation matrix
    """
    result = df[column_names].corr(method=method)
    message = f"#### Correlation between {', '.join(column_names)}\n\n{result.to_markdown()}"
    
    send_thinking_step(func="correlation", content=message)
    return result
