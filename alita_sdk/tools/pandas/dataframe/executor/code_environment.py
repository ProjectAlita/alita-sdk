"""Module to import optional dependencies.

Source: Taken from pandas/compat/_optional.py
"""

import importlib
import types
from typing import List, Optional, Union
from ..utils import send_thinking_step
# Import all stats methods for execution environment
from ...statsmodels.base_stats import (
    convert_str_column_to_categorical, 
    convert_categorical_colum_to_numeric,
    label_based_on_bins,
    descriptive_statistics,
    standardize,
    crosstab,
    _test_a_model,
    _prepare_dataset
)

from ...statsmodels.descriptive import (
    calculate_skewness_and_kurtosis,
    calculate_mode,
    calculate_range,
    calculate_variance,
    delimitred_column_values_to_list,
    explode,
    correlation,
    covariance,
    pairwise_correlation
)

from ...statsmodels.hypothesis_testing import (
    one_sample_t_test,
    two_sample_t_test,
    one_way_ANOVA,
    two_way_ANOVA,
    kruskal_wallis_test,
    chi_square_test,
    chi_square_test_on_data,
    bartlett_test,
    KMO_test,
    mann_whitney_test,
    wilcoxon_test
)

from ...statsmodels.regression import (
    linear_regression,
    logistic_regression,
    mixed_effect_lm,
    predict,
    factorAnalysis,
    principal_component_analysis_2D
)

INSTALL_MAPPING = {}


def get_version(module: types.ModuleType) -> str:
    """Get the version of a module."""
    version = getattr(module, "__version__", None)

    if version is None:
        raise ImportError(f"Can't determine version for {module.__name__}")

    return version

def get_environment() -> dict:
    """
    Returns the environment for the code to be executed.

    Returns (dict): A dictionary of environment variables
    """
    env = {
        "List": List,
        "Optional": Optional,
        "Union": Union,
        "pd": import_dependency("pandas"),
        "plt": import_dependency("matplotlib.pyplot"),
        "np": import_dependency("numpy"),
        "sklearn": import_dependency("sklearn"),
        "statsmodels": import_dependency("statsmodels"),
        "factor_analyzer": import_dependency("factor_analyzer"),
        "ss": import_dependency("scipy.stats"),
        "sm": import_dependency("statsmodels.api"),
        "send_thinking_step": send_thinking_step,
        "result": None,
        
        # Add base_stats methods
        "convert_str_column_to_categorical": convert_str_column_to_categorical,
        "convert_categorical_colum_to_numeric": convert_categorical_colum_to_numeric,
        "label_based_on_bins": label_based_on_bins,
        "descriptive_statistics": descriptive_statistics,
        "standardize": standardize,
        "crosstab": crosstab,
        "_test_a_model": _test_a_model,
        "_prepare_dataset": _prepare_dataset,
        
        # Add descriptive stats methods
        "calculate_skewness_and_kurtosis": calculate_skewness_and_kurtosis,
        "calculate_mode": calculate_mode,
        "calculate_range": calculate_range,
        "calculate_variance": calculate_variance,
        "delimitred_column_values_to_list": delimitred_column_values_to_list,
        "explode": explode,
        "correlation": correlation,
        "covariance": covariance,
        "pairwise_correlation": pairwise_correlation,
        
        # Add hypothesis testing methods
        "one_sample_t_test": one_sample_t_test,
        "two_sample_t_test": two_sample_t_test,
        "one_way_ANOVA": one_way_ANOVA,
        "two_way_ANOVA": two_way_ANOVA,
        "krushkal_wallis_test": kruskal_wallis_test,
        "chi_square_test": chi_square_test,
        "chi_square_test_on_data": chi_square_test_on_data,
        "bartlett_test": bartlett_test,
        "KMO_test": KMO_test,
        "mann_whitney_test": mann_whitney_test,
        "wilcoxon_test": wilcoxon_test,
        
        # Add regression methods
        "linear_regression": linear_regression,
        "logistic_regression": logistic_regression,
        "mixed_effect_lm": mixed_effect_lm,
        "predict": predict,
        "factorAnalysis": factorAnalysis,
        "principal_component_analysis_2D": principal_component_analysis_2D,
    }

    return env


def import_dependency(
    name: str,
    extra: str = "",
    errors: str = "raise",
):
    """
    Import an optional dependency.

    By default, if a dependency is missing an ImportError with a nice
    message will be raised. If a dependency is present, but too old,
    we raise.

    Args:
        name (str): The module name.
        extra (str): An additional text to include in the ImportError message.
        errors (str): Representing an action to do when a dependency
            is not found or its version is too old.
            Possible values: "raise", "warn", "ignore":
                * raise : Raise an ImportError
                * warn : Only applicable when a module's version is too old.
                  Warns that the version is too old and returns None
                * ignore: If the module is not installed, return None, otherwise,
                  return the module, even if the version is too old.
                  It's expected that users validate the version locally when
                  using ``errors="ignore"`` (see. ``io/html.py``)
        min_version (str): Specify a minimum version that is different from
            the global pandas minimum version required. Defaults to None.

    Returns:
         Optional[module]:
            The imported module, when found and the version is correct.
            None is returned when the package is not found and `errors`
            is False, or when the package's version is too old and `errors`
            is `'warn'`.
    """

    assert errors in {"warn", "raise", "ignore"}

    package_name = INSTALL_MAPPING.get(name)
    install_name = package_name if package_name is not None else name

    msg = (
        f"Missing optional dependency '{install_name}'. {extra} "
        f"Use pip or conda to install {install_name}."
    )
    try:
        module = importlib.import_module(name)
    except ImportError as exc:
        if errors == "raise":
            raise ImportError(msg) from exc
        return None

    return module