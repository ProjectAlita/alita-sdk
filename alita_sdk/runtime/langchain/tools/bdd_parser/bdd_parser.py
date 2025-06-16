import functools
import os
import re
import string
from typing import Generator, Any

import numpy as np
import pandas as pd
from pandas import DataFrame

from .parser import parse_feature, ScenarioTemplate

TAG_VALUES_TO_FILTER_OUT = ['qa1', 'stage', 'qa2', 'dev7', 'dev3', 'stage2', 'prod', 'ctr', 'pty', 'mks', 'leq', 'mk',
                            'lq', 'atm', 'atm ', 'at', 'sc', 'odp', 'wodp', 'dev4', 'perf2', 'perf', 'ondemand', 'stg',
                            'qa4', 'dev5', 'dev6', 'dev6', 'qa5', 'qa3', 'fr', 'en', 'e2e', 'sit',
                            'dev2', 'positive', 'negative', 'prefer']


def get_all_scenarios_from_directory(directory_name: str):
    """
    :param directory_name: The name of the directory to search for feature files.
    :return: A generator of ScenarioTemplate objects representing all the scenarios found in the directory and its subdirectories.
    """
    for root, dirs, files in os.walk(directory_name):
        for filename in files:
            if filename.endswith('.feature'):
                yield from parse_feature(root, filename).scenarios
            if filename.endswith('.story'):
                yield from parse_feature(root, filename, is_jbehave_story=True).scenarios


def get_initial_steps_data_frame(scenarios: Generator[ScenarioTemplate, Any, None]) -> DataFrame:
    """
    :param scenarios: A list of ScenarioTemplate objects representing the scenarios.
    :return: A pandas DataFrame object containing the initial steps' data.

    This method takes a list of ScenarioTemplate objects and creates a pandas DataFrame object with columns representing various information about the steps in the scenarios. Each row in the DataFrame represents a single step.

    The 'Tags' column in the DataFrame contains the tags associated with the scenario that the step belongs to.
    The 'Embeddings Source' column contains the step name after removing any HTML tags and multiple whitespace characters. Also, the example table parameter is removed.
    The 'Original Step' column contains the original step name as it appears in the scenario.
    The 'BDD Keyword' column contains the BDD keyword associated with the step type, with the first letter capitalized.

    Example usage:
    ```
    from parser import parse_feature, ScenarioTemplate

    # Assuming scenarios is a list of ScenarioTemplate objects
    data_frame = get_initial_steps_data_frame(scenarios)
    ```
    """
    embeddings_generator = (
        # [value.tags, re.sub(' +', ' ', re.sub("'<.*?>'", '', step.name)), step.name, string.capwords(step.type)]
        [value.tags, step.name.split('\n')[0], step.name, string.capwords(step.type)]
        for value in scenarios for step in value.steps
    )
    data_array = np.array(list(embeddings_generator))
    df = pd.DataFrame(data_array, columns=['Tags', 'Embeddings Source', 'Original Step', 'BDD Keyword'])
    return df


def create_scenarios_data_frame(scenarios: Generator[ScenarioTemplate, Any, None]) -> DataFrame:
    embeddings_generator = (
        [scenario.name,
         '\n'.join([string.capwords(step.type) + ' ' + step.name for step in scenario.steps]),
         'Examples:' + '\n' + '\t' + '|' + '|'.join(
             scenario.examples.example_params) + '|' + '\n' + '\t' + '|' + '|'.join(
             scenario.examples.examples[0]) + '|' if scenario.examples.examples else '',
         ", ".join(scenario.tags)
         ]
        for scenario in scenarios if ('utils' not in scenario.tags) or ('util' not in scenario.tags)
    )
    data_array = np.array(list(embeddings_generator))
    return pd.DataFrame(data_array, columns=['Scenario Name', 'Scenario', 'Test Data', 'Tags'])


def get_first_instance(df: DataFrame) -> DataFrame:
    """
    :param df: A pandas DataFrame containing the data to be processed.
    :return: A pandas DataFrame with the first instance of each 'Original Step' group, where 'Original Step' is a column in the DataFrame.

    This method takes a DataFrame as input and performs the following operations:
    1. Groups the DataFrame by the 'Original Step' column.
    2. Aggregates the 'Tags' column within each group by applying a union operation on the sets of tags.
    3. Takes the first value from the 'Embeddings Source' column within each group.
    4. Resets the index of the DataFrame.
    5. Applies the set function to the 'Tags' column to ensure each set contains unique items.
    6. Returns the resulting DataFrame with the processed data.
    """
    df = df.groupby('Original Step').agg({'Tags': lambda x: functools.reduce(set.union, x),
                                          'Embeddings Source': 'first'})
    df.reset_index(inplace=True)
    df['Tags'] = df['Tags'].apply(list)
    return df


def get_keyword(df: DataFrame) -> DataFrame:
    """

    :param df: A pandas DataFrame containing the 'BDD Keyword' and 'Original Step' columns. The 'BDD Keyword' column should contain the BDD keywords for each step, and the 'Original Step' column should contain the original steps.
    :return: A new DataFrame with the 'BDD Keyword' column containing the most frequently occurring BDD keyword for each unique original step.

    """
    df = df['BDD Keyword'].groupby(df['Original Step']).agg(lambda x: x.value_counts().index[0]).reset_index()
    df.rename(columns={'BDD Keyword': 'BDD Keyword'}, inplace=True)
    return df


def get_count(df: DataFrame) -> DataFrame:
    """
    Get the count of each combination of 'Original Step' and 'BDD Keyword' in the given DataFrame.

    :param df: The DataFrame containing the data.
    :return: The DataFrame with the count of each combination.
    """
    df = df.groupby(['Original Step', 'BDD Keyword']).size().unstack(fill_value=0)
    df['Overall Count'] = df.sum(axis=1)
    df.reset_index(inplace=True)
    return df


def get_final_data_frame(df_first_instance: DataFrame, df_keyword: DataFrame, df_with_count: DataFrame) -> DataFrame:
    """
    Method: get_final_data_frame

    This method takes three parameters: df_first_instance (DataFrame), df_keyword (DataFrame), and df_with_count (DataFrame).
    It performs inner joins on the three dataframes and returns a new DataFrame.

    Parameters:
        - df_first_instance (DataFrame): The first DataFrame to be merged.
        - df_keyword (DataFrame): The second DataFrame to be merged.
        - df_with_count (DataFrame): The third DataFrame to be merged.

    Returns:
        - df (DataFrame): The merged DataFrame.

    Example Usage:
        df_first_instance = pd.DataFrame(...)
        df_keyword = pd.DataFrame(...)
        df_with_count = pd.DataFrame(...)
        result = get_final_data_frame(df_first_instance, df_keyword, df_with_count)
    """
    df = pd.merge(df_first_instance, df_keyword, on='Original Step', how='inner', sort=False)
    df = pd.merge(df, df_with_count, on='Original Step', how='inner', sort=False)
    return df


def filter_tags(df: DataFrame) -> DataFrame:
    """
    Filter the given DataFrame based on specified tags.

    :param df: The DataFrame to be filtered. It should contain a column named 'Tags'.
    :return: The filtered DataFrame.

    """
    df['Tags'] = df['Tags'].apply(lambda tags: {tag for tag in tags if
                                                tag not in TAG_VALUES_TO_FILTER_OUT
                                                and not re.search(r"([A-Z]+|[a-z]+)-", tag) and not re.search(
                                                    r"(week|sprint|option|smoke|demo|regression|issue)", tag,
                                                    re.IGNORECASE) and not tag.__contains__(
                                                    'RC') and not tag.__contains__('develop') and not tag.__contains__(
                                                    'debug') and tag and not re.search(r"[0-9]+",
                                                                                       tag) and not re.search(
                                                    r"[A-Z]+[0-9]+-", tag) and not re.search(r"[A-Z]+_", tag)})
    return df


def convert_tags_to_list(df: DataFrame) -> DataFrame:
    """
    Convert the 'Tags' column from a set to a list.

    :param df: The DataFrame containing the data.
    :return: The DataFrame with the 'Tags' column converted to a list.
    """
    df['Tags'] = df['Tags'].apply(list)
    return df


def normalize_parameter_names(step: str) -> str:
    """
    Normalize the parameter names in a step.

    :param step: The step to normalize.
    :return: The normalized step.
    """
    return re.sub(r"\".*?\"|'.*?'|<.*?>|'<.*?>'|\"<.*?>\"", "'value'", step)


def merge_semantically_similar_steps(df: DataFrame) -> DataFrame:
    """
    Merge semantically similar steps in the DataFrame.

    :param df: The DataFrame containing the data.
    :return: The DataFrame with semantically similar steps merged.
    """
    df['Normalized Embeddings Source'] = df['Embeddings Source'].apply(normalize_parameter_names)
    df = df.groupby('Normalized Embeddings Source').agg({
        'Original Step': lambda x: list(x),
        'Tags': lambda x: set.union(*x),
        'Embeddings Source': 'first',
        'Given': 'sum',
        'When': 'sum',
        'Then': 'sum',
        'Overall Count': 'sum'
    })
    df['BDD Keyword'] = df[['Given', 'When', 'Then']].idxmax(axis=1)
    df.reset_index(drop=True, inplace=True)
    return df


def extract_all_tags(df: DataFrame) -> set:
    """
    Extracts all the tags for all the available BDD steps.

    :param df: The DataFrame containing the data.
    :return: A set containing all the tags.
    """
    all_tags = set()
    for tags in df['Tags']:
        all_tags.update(tags)
    return all_tags
