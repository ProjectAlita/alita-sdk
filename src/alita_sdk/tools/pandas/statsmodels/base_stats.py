from typing import Dict, List, Optional
import sklearn
import pandas as pd
from ..dataframe.utils import send_thinking_step

def convert_str_column_to_categorical(df: pd.DataFrame, column_name: str, numeric_column_name: str) -> str:
    """ Convert string column to categorical column with numeric reprenrarion - adds new column to dataset.
    Args:
        df (pd.DataFrame): DataFrame to operate on
        column_name (str): Column name
        numeric_column_name (str): Name for the created numeric column
    
    Returns:
        str: Name of the created numeric column
    """
    df[column_name] = pd.Categorical(df[column_name])
    return convert_categorical_colum_to_numeric(df, column_name, numeric_column_name)

def convert_categorical_colum_to_numeric(df: pd.DataFrame, column_name: str, numeric_column_name: str) -> str:
    """ Convert categorical column to numeric column - adds new column to dataset.
    Args:
        df (pd.DataFrame): DataFrame to operate on
        column_name (str): Column name
        numeric_column_name (str): Name for the created numeric column
    
    Returns:
        str: Name of the created numeric column
    """
    # Ensure the column is categorical type before accessing .cat
    if not pd.api.types.is_categorical_dtype(df[column_name]):
        df[column_name] = pd.Categorical(df[column_name])
    
    # Create the numeric column directly from categorical codes
    df[numeric_column_name] = df[column_name].cat.codes
    
    # Build a mapping from category values to their numeric codes
    result = f'{column_name} categorical column values corresponds to {numeric_column_name} values: '
    
    # Use simple iteration over categories and their corresponding codes (0, 1, 2, ...)
    for i, category in enumerate(df[column_name].cat.categories):
        result += f'Value: {category} corresponds to {i} | '
    
    send_thinking_step(func="convert_categorical_colum_to_numeric", content=result)
    
    return numeric_column_name


def label_based_on_bins(df: pd.DataFrame, column_name: str, bins: List[float], labels: List[str], 
                     labeled_column_name: str, numeric_column_name: str) -> Dict[str, any]:
    """ Categorize column based on integer or float bins and add new column with labels culumns needs to be numeric or categorical before binning
    Args:
        df (pd.DataFrame): DataFrame to operate on
        column_name (str): Column name
        bins (List[float]): List of bin values
        labels (List[str]): List of labels for each bin
        labeled_column_name (str): Name for the created labeled column
        numeric_column_name (str): Name for the created numeric column
    
    Returns:
        Dict[str, any]: Dictionary containing:
            - labeled_column_name (str): Name of the created labeled column
            - numeric_column_name (str): Name of the created numeric column
            - bin_counts (dict): Count of values in each bin
            - bin_percentages (dict): Percentage of values in each bin
            - bin_statistics (pd.DataFrame): DataFrame with bin counts and percentages
    """
    if len(bins) != len(labels)+1:
        error_message = f"ERROR: Number of bins should be equal to number of labels + 1."
        send_thinking_step(func="label_based_on_bins", content=error_message)
        raise ValueError(error_message)
    
    df[labeled_column_name] = pd.cut(df[column_name], bins=bins, labels=labels)
    convert_categorical_colum_to_numeric(df, labeled_column_name, numeric_column_name)
    
    # Calculate bin counts and percentages
    bin_counts = df[labeled_column_name].value_counts().to_dict()
    total_values = len(df[labeled_column_name].dropna())
    bin_percentages = {k: round(v / total_values * 100, 2) for k, v in bin_counts.items()}
    
    # Create a DataFrame with bin statistics for easier analysis
    bin_statistics = pd.DataFrame({
        'Count': bin_counts,
        'Percentage': bin_percentages
    })
    bin_statistics = bin_statistics.sort_index()  # Sort by bin labels
    
    # Format the binning results for the message
    bin_results = "Binning results:\n"
    bin_results += f"{'Bin Label':<15} {'Count':<10} {'Percentage':<10}\n"
    bin_results += "-" * 35 + "\n"
    
    for label in labels:
        count = bin_counts.get(label, 0)
        percentage = bin_percentages.get(label, 0)
        bin_results += f"{str(label):<15} {count:<10} {percentage}%\n"
    
    message = f'Added new columns: {labeled_column_name} and {numeric_column_name} that are labeled representation of {column_name} and numeric representation of labels.\n\n'
    message += bin_results
    send_thinking_step(func="label_based_on_bins", content=message)
    
    # Return both column names and bin statistics
    return {
        'labeled_column_name': labeled_column_name,
        'numeric_column_name': numeric_column_name,
        'bin_counts': bin_counts,
        'bin_percentages': bin_percentages,
        'bin_statistics': bin_statistics
    }


def descriptive_statistics(df: pd.DataFrame, columns: List[str], 
                           metrics: Optional[List[str]]=None, 
                           group_by: Optional[List[str]]=None, 
                           group_by_value: Optional[str]=None,
                           n_limit: Optional[int]=None) -> pd.DataFrame:
    """Calculate the descriptive statistics for single or list of columns, if group_by is provided, calculate the statistics per group
    Args:
        df (pd.DataFrame): DataFrame to operate on
        columns (List[str]): list of columns to calculate statistics for
        metrics (List[str], optional): list of metrics to calculate, available metrics are mean, median, std, min, max, count, 25%, 50%, 75%.
            These will be available in the returned DataFrame as MultiIndex columns, e.g. ('column_name', 'mean').
        group_by (List[str], optional): list of columns to group by, defaults to None.
        group_by_value (str, optional): could used when there is only one column to group by applies as filter defaults value to None.
        n_limit (int, optional): limit the number of rows returned, defaults to None.
        
    Returns:
        pd.DataFrame: DataFrame containing descriptive statistics with MultiIndex columns.
            When group_by is used, access statistics with df[('column_name', 'metric_name')], e.g. df[('Survived', 'mean')]
    """
    if n_limit:
        n_limit = int(n_limit) if isinstance(n_limit, str) else n_limit
    if metrics is None:
        metrics = ['mean', 'std', 'min', 'max', 'count', '25%', '50%', '75%']
    if group_by is None:
        result = df[columns].describe()
    else:
        if group_by_value and len(group_by) == 1:
            try:
                group_by_value = float(group_by_value)
            except ValueError:
                pass
            result = df[df[group_by[0]] == group_by_value][columns].describe()
        else:
            result = df.groupby(group_by)[columns].describe()
    if n_limit and len(result) > n_limit:
        result = result.head(n_limit)
    send_thinking_step(func="descriptive_statistics", content=f"Descriptive statistics for columns {', '.join(columns)}:\n\n{result.to_markdown()}")
    return result
    

def standardize(df: pd.DataFrame, column_names: List[str], std_column_suffix: str = "_std") -> List[str]:
    """standardize the dataset features onto unit scale (mean = 0 and variance = 1) which is a requirement for the optimal performance of many machine learning algorithm. Adds new columns to dataset.
    Args:
        df (pd.DataFrame): DataFrame to operate on
        column_names (List[str]): List of column names containing features to standardize
        std_column_suffix (str): Suffix to append to column names for standardized columns (required)
    
    Returns:
        List[str]: Names of the created standardized columns
    """
    _df = df.loc[:, column_names].values
    _df = sklearn.preprocessing.StandardScaler().fit_transform(_df)
    new_columns = []
    for i, c in enumerate(column_names):
        new_column = f"{c}{std_column_suffix}"
        new_columns.append(new_column)
        df[new_column] = _df[:, i]
    
    message = f"Added new columns with standardized values: {', '.join(new_columns)}, Sample of data stored there: {df[new_columns].head(5).to_string()}"
    send_thinking_step(func="standardize", content=message)
    
    return new_columns


def crosstab(df: pd.DataFrame, columns: List[str]) -> str:
    """Compute a simple cross tabulation between multiple categorical or numeric columns.
    Args:
        df (pd.DataFrame): DataFrame to operate on
        columns (List[str]): list of columns where first column is used as index, other columns are used as columns
        
    Returns:
        str: CSV representation of the cross tabulation
    """
    index_col = columns[0]
    cols = [df[c] for c in columns[1:]]
    result = pd.crosstab(index=df[index_col], columns=cols)
    return result.to_csv()


def _test_a_model(model, features, target) -> float:
    """Test model accuracy by predicting target values and comparing with actual values
    Args:
        model: The trained model to test
        features: Feature data to predict from
        target: Actual target values to compare against
        
    Returns:
        float: The model's accuracy
    """
    pred = model.predict(features)
    prediction = list(map(round, pred)) 
    _accuracy = sklearn.metrics.accuracy_score(target, prediction)
    send_thinking_step(func="_test_a_model", content=f"Model accuracy: {_accuracy}")
    return _accuracy

def _prepare_dataset(df: pd.DataFrame, columns_set_one: List[str], columns_set_two: Optional[List[str]]=None) -> tuple:
    """Prepare dataset for model training by selecting columns and handling missing values
    Args:
        df (pd.DataFrame): DataFrame to operate on
        columns_set_one (List[str]): First set of columns
        columns_set_two (List[str], optional): Second set of columns, defaults to None
        
    Returns:
        tuple: (_df, columns_set_one, columns_set_two) - Cleaned DataFrame and column sets
    """
    if columns_set_two is None:
        columns_set_two = []
    
    _df = df[columns_set_one + columns_set_two]
    _df = _df.dropna()
    if len(columns_set_one) == 1:
        columns_set_one = columns_set_one[0]
    if len(columns_set_two) == 1:
        columns_set_two = columns_set_two[0]
    return _df, columns_set_one, columns_set_two