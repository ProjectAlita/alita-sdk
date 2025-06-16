"""
Statistical model tools for pandas dataframes.
This module provides functions for statistical analysis, hypothesis testing, and regression modeling.
"""

import inspect
from .base_stats import (
    convert_str_column_to_categorical, 
    convert_categorical_colum_to_numeric,
    label_based_on_bins,
    descriptive_statistics,
    standardize,
    crosstab
)

from .descriptive import (
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

from .hypothesis_testing import (
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

from .regression import (
    linear_regression,
    logistic_regression,
    mixed_effect_lm,
    predict,
    factorAnalysis,
    principal_component_analysis_2D
)

def _generate_function_docs(func, with_examples=True):
    """Generate documentation for a function in the expected format."""
    full_doc = func.__doc__ or ""
    full_doc = full_doc.strip()
    # Get the first line of docstring for the brief description
    brief_doc = full_doc.split('\n')[0]
    
    # Extract parameter descriptions from Args section
    param_descriptions = {}
    if "Args:" in full_doc:
        try:
            args_section = full_doc.split("Args:")[1].strip()
            end_idx = args_section.find("\n\n")
            if end_idx > 0:
                args_section = args_section[:end_idx]
            
            # Parse parameter descriptions, typically in format: "param_name (type): description"
            current_param = None
            current_desc = []
            
            for line in args_section.split('\n'):
                line = line.strip()
                if not line:
                    continue
                    
                # Check if line starts a new parameter
                if line and ":" in line and not line.startswith(" "):
                    # Save previous parameter if there was one
                    if current_param and current_desc:
                        param_descriptions[current_param] = " ".join(current_desc)
                    
                    # Parse new parameter
                    parts = line.split(':', 1)
                    param_part = parts[0].strip()
                    param_name = param_part.split('(')[0].strip() if '(' in param_part else param_part
                    
                    current_param = param_name
                    current_desc = [parts[1].strip()] if len(parts) > 1 else []
                elif current_param:  # It's a continuation of the previous parameter description
                    current_desc.append(line)
            
            # Don't forget the last parameter
            if current_param and current_desc:
                param_descriptions[current_param] = " ".join(current_desc)
        except Exception:
            # If parsing fails, continue without parameter descriptions
            pass
    
    # Extract return description from docstring if available
    return_desc = ""
    if "Returns:" in full_doc:
        try:
            return_section = full_doc.split("Returns:")[1].strip()
            # The return description typically follows a format like "ReturnType: Description"
            # or is indented with spaces
            return_desc_lines = []
            for line in return_section.split('\n'):
                line = line.strip()
                if line and not line.startswith("Args:") and not line.startswith("---"):
                    return_desc_lines.append(line)
                # Stop if we hit another major section
                if line.endswith(":") and not line.startswith(")"):
                    break
            if return_desc_lines:
                return_desc = " - " + " ".join(return_desc_lines)
                # Clean up any type information at the beginning (e.g., "List[str]: Names of...")
                if ":" in return_desc:
                    return_desc = return_desc.split(":", 1)[1].strip()
        except Exception:
            # If parsing fails, we'll just use the brief description
            pass
    
    # Get the actual function parameters using inspect
    try:
        signature = inspect.signature(func)
        
        # Helper function to format type annotations
        def format_type_annotation(annotation):
            if annotation == inspect.Parameter.empty:
                return "Any"
            # Convert all annotations to string format
            return str(annotation).replace("typing.", "").replace("<class '", "").replace("'>", "")
        
        # Format the parameters string with descriptions where available
        params_list = []
        for param_name, param in signature.parameters.items():
            param_type = format_type_annotation(param.annotation)
            param_default = f' = {repr(param.default)}' if param.default != inspect.Parameter.empty else ''
            
            # Add description if available
            param_desc = ""
            if param_name in param_descriptions:
                # Clean up the description by removing quotes if present
                desc = param_descriptions[param_name]
                desc = desc.strip('"').strip("'")
                param_desc = f" # {desc}"
            
            params_list.append(f"{param_name}: {param_type}{param_default}{param_desc}")
        
        params_str = ", ".join(params_list)
        
        # Get the return type annotation
        return_type = signature.return_annotation
        return_type_str = format_type_annotation(return_type)
        
        # Append return description if available
        if return_desc:
            return_type_str = f"{return_type_str}{return_desc}"
    except Exception as e:
        # Fallback if inspection fails
        params_str = "df: pd.DataFrame, **kwargs"
        return_type_str = "Any"
        
    return f"<function>\ndef {func.__name__}({params_str}) -> {return_type_str}:\n    '''{brief_doc}'''\n</function>"

# Group functions by category
function_categories = {
    "Basic Statistical Functions": [
        convert_str_column_to_categorical,
        convert_categorical_colum_to_numeric,
        label_based_on_bins,
        descriptive_statistics,
        standardize,
        crosstab
    ],
    "Descriptive Statistics Functions": [
        calculate_skewness_and_kurtosis,
        calculate_mode,
        calculate_range,
        calculate_variance,
        explode,
        delimitred_column_values_to_list,
        covariance,
        correlation,
        pairwise_correlation
    ],
    "Hypothesis Testing Functions": [
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
    ],
    "Regression and Machine Learning Functions": [
        linear_regression,
        logistic_regression,
        mixed_effect_lm,
        predict,
        factorAnalysis,
        principal_component_analysis_2D
    ]
}

# Build the prompt_addon dynamically
prompt_addon_parts = ["The following statistical analysis functions are available in the environment and can be used directly:"]

for category, functions in function_categories.items():
    prompt_addon_parts.append(f"\n--- {category} ---\n")
    for func in functions:
        prompt_addon_parts.append(_generate_function_docs(func))

prompt_addon = "\n\n".join(prompt_addon_parts)

__all__ = [
    # base_stats
    'convert_str_column_to_categorical', 
    'convert_categorical_colum_to_numeric',
    'label_based_on_bins',
    'descriptive_statistics',
    'standardize',
    'crosstab',
    
    # descriptive
    'calculate_skewness_and_kurtosis',
    'calculate_mode',
    'calculate_range',
    'calculate_variance',
    'delimitred_column_values_to_list',
    'explode',
    'correlation',
    'covariance',
    'pairwise_correlation',
    
    # hypothesis_testing
    'one_sample_t_test',
    'two_sample_t_test',
    'one_way_ANOVA',
    'two_way_ANOVA',
    'krushkal_wallis_test',
    'chi_square_test',
    'chi_square_test_on_data',
    'bartlett_test',
    'KMO_test',
    'mann_whitney_test',
    'wilcoxon_test',
    
    # regression
    'linear_regression',
    'logistic_regression',
    'mixed_effect_lm',
    'predict',
    'factorAnalysis',
    'principal_component_analysis_2D',
    
    # prompt addon
    'prompt_addon'
]