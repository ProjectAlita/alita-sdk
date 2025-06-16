import pandas as pd
from typing import List, Union, Optional, Dict
import statsmodels.api as sm
import sklearn
import factor_analyzer
import numpy as np
from ..dataframe.utils import send_thinking_step
from .base_stats import _prepare_dataset, _test_a_model

def linear_regression(df: pd.DataFrame, feature_columns: List[str], formula: str, target_column: str, model=None) -> tuple:
    """ Build model to predict a dependent variable using two or more predictor variables
    Args:
        df (pd.DataFrame): DataFrame to operate on
        feature_columns (List[str]): Column names for linear regression. Should be full list of columns used within R formula
        formula (str): "R formula for representing relationship between dependent and independent variables"
        target_column (str): "target column we will be predicting"
        model: Optional model object where the trained model will be stored
        
    Returns:
        tuple: (accuracy, summary) - Model accuracy and summary
    """
    
    _df, feature_columns, target_column = _prepare_dataset(df, feature_columns, target_column)
    trained_model = sm.formula.api.ols(formula, data=_df).fit()
    if model is not None:
        model = trained_model
    accuracy = _test_a_model(trained_model, _df[feature_columns], _df[target_column])
    message = f"""#### Linear regression model summary ({accuracy}):\n\n```\n\n"""
    message += trained_model.summary().as_text().replace('\n', '\n\n')
    message += "\n\n```\n\n"""
    
    send_thinking_step(func="linear_regression", content=message)
    return accuracy, trained_model.summary()


def logistic_regression(df: pd.DataFrame, feature_columns: List[str], formula: str, target_column: str, model=None) -> tuple:
    """ Build model to predict of probability of occurrence of an event
    Args:
        df (pd.DataFrame): DataFrame to operate on
        feature_columns (List[str]): Column names for logistic regression. Should be full list of columns used within R formula
        formula (str): "R formula for representing relationship between dependent and independent variables"
        target_column (str): "target column we will be predicting"
        model: Optional model object where the trained model will be stored
        
    Returns:
        tuple: (accuracy, summary) - Model accuracy and summary
    """
    
    _df, feature_columns, target_column = _prepare_dataset(df, feature_columns, target_column)
    trained_model = sm.formula.api.logit(formula, data=_df).fit()
    if model is not None:
        model = trained_model
    accuracy = _test_a_model(trained_model, _df[feature_columns], _df[target_column])
    message = f"""#### Logistic regression model summary ({accuracy}):\n\n```\n\n"""
    message += trained_model.summary().as_text().replace('\n', '\n\n')
    message += "\n\n```\n\n"""
    
    send_thinking_step(func="logistic_regression", content=message)
    return accuracy, trained_model.summary()


def mixed_effect_lm(df: pd.DataFrame, feature_columns: List[str], formula: str, group_column: str, target_column: str, model=None) -> tuple:
    """ Build a mixed effect model for regression analysis involving dependent data, random effects must be independently-realized for responses in different groups
    Args:
        df (pd.DataFrame): DataFrame to operate on
        feature_columns (List[str]): Column names for mixed effect model. Should be full list of columns used within R formula
        formula (str): "R formula for representing relationship between variables"
        group_column (str): "column name with group values"
        target_column (str): "target column, to be used in testing of model"
        model: Optional model object where the trained model will be stored
        
    Returns:
        tuple: (accuracy, summary) - Model accuracy and summary
    """
    all_columns = feature_columns + [group_column]
    _df = df[all_columns + [target_column]].dropna()
    
    trained_model = sm.formula.api.mixedlm(formula, _df, groups=_df[group_column]).fit()
    if model is not None:
        model = trained_model
    accuracy = _test_a_model(trained_model, _df[feature_columns], _df[target_column])
    message = f"""#### Mixed effect model summary ({accuracy}):\n\n```\n\n"""
    message += trained_model.summary().as_text().replace('\n', '\n\n')
    message += "\n\n```\n\n"""
    
    send_thinking_step(func="mixed_effect_lm", content=message)
    return accuracy, trained_model.summary()
    


def predict(df: pd.DataFrame, feature_columns: List[str], feature_values: List[float], model=None) -> Union[np.ndarray, str]:
    """ Predict target column values using trained model
    Args:
        df (pd.DataFrame): DataFrame to operate on
        feature_columns (List[str]): List of feature column names
        feature_values (List[float]): List of feature values for prediction
        model: Trained model object to use for prediction
        
    Returns:
        numpy.ndarray or str: Prediction results or error message if model is not trained
    """
    predict_ds = pd.DataFrame([feature_values], columns=feature_columns)
    if model is None:
        return "ERROR: Model is not trained yet. Please use one of the model training actions first"

    predictions = model.predict(predict_ds)
    message = f"""#### Predictions for:\n\n {', '.join(feature_columns)}: {', '.join([str(round(x, 4)) for x in predictions])}"""
    message += f"""##### Results:\n\n {', '.join([str(round(x, 4)) for x in predictions])}"""
    
    send_thinking_step(func="predict", content=message)
    return predictions



def factorAnalysis(df: pd.DataFrame, columns: List[str]) -> tuple:
    """ Factor analysis used to describe variability among observed, correlated variables in terms of a potentially lower number of unobserved variables called factors; KMO calculation included and score less than 0.6 is considered inadequate
    Args:
        df (pd.DataFrame): DataFrame to operate on
        columns (List[str]): List of column names for factor analysis
        
    Returns:
        tuple: (eigenvalues, factor_variance, kmo) - Analysis results
    """
    _df, _, _ = _prepare_dataset(df, columns)
    _, kmo_model = factor_analyzer.factor_analyzer.calculate_kmo(_df)
    if kmo_model < 0.6:
        result = f"WARNING: KMO score is {kmo_model}, which is less than 0.6, so factor analysis is not recommended"
        send_thinking_step(func="factorAnalysis", content=result)
        return None, None, kmo_model
        
    fa = factor_analyzer.FactorAnalyzer()
    # Identify number of factors using eigenvalues
    fa.analyze(_df, 25, rotation=None)
    ev, v = fa.get_eigenvalues()
    max_factors = 0
    for i in range(len(ev)):
        if ev[i] < 1:
            break
        else:
            max_factors = i + 1
    
    # Running analysis
    fa.analyze(_df, max_factors, rotation="varimax")
    statistics= fa.get_factor_variance()
    
    # Interpreting results
    result = "| | "+" | ".join([f"Factor {i}" for i in range(1, max_factors + 1)]) + " | \n"
    result += "| SS Loadings | " + " | ".join([str(round(x, 4)) for x in statistics[0].tolist()]) + " |\n"
    result += "| Proportion Var | " + " | ".join([str(round(x, 4)) for x in statistics[1].tolist()]) + " |\n"
    result += "| Cumulative Var | " + " | ".join([str(round(x, 4)) for x in statistics[2].tolist()]) + " |\n"
    # Formatting message to markdown
    message = f"""#### Factor analysis results:\n\n{result}"""
    
    send_thinking_step(func="factorAnalysis", content=message)
    return ev, statistics, kmo_model


def principal_component_analysis_2D(df: pd.DataFrame, feature_columns: List[str], target_column: str, 
                               pc_x_column: str, pc_y_column: str) -> Dict[str, str]:
    """ Principal component analysis (PCA) to decreases dementiality of data to 2 dimentions, very usefull in 2D data visualization. Adds new columns to dataset.
    Args:
        df (pd.DataFrame): DataFrame to operate on
        feature_columns (List[str]): List of column names containing features
        target_column (str): Column name with target values
        pc_x_column (str): Name for the first principal component column
        pc_y_column (str): Name for the second principal component column
        
    Returns:
        Dict[str, str]: Dictionary with keys 'pc_x' and 'pc_y' containing the names of the created principal component columns
    """
    _df = df.loc[:, feature_columns].values
    _df = sklearn.preprocessing.StandardScaler().fit_transform(_df)
    
    pca = sklearn.decomposition.PCA(n_components=2)

    principalComponents = pca.fit_transform(_df)
    
    df[pc_x_column] = principalComponents[:, 0]
    df[pc_y_column] = principalComponents[:, 1]
    
    result = f"Added new columns with principal components values: {pc_x_column}, {pc_y_column} from features columns {', '.join(feature_columns)}. Data sample: {df[[pc_x_column, pc_y_column, target_column]].head(5).to_string()}"
    send_thinking_step(func="principal_component_analysis_2D", content=result)
    
    return {
        "pc_x": pc_x_column,
        "pc_y": pc_y_column
    }
