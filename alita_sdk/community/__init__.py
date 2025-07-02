"""
Alita SDK Community Module

This module contains community extensions and utilities for the Alita SDK.
Includes analysis tools, browser automation, research tools, and exploratory data analysis.
"""

import importlib

# Import available community modules
__all__ = []

# Standard module imports with fallback
_modules = ['utils', 'analysis', 'deep_researcher', 'eda']

for module_name in _modules:
    try:
        module = importlib.import_module(f'.{module_name}', package=__name__)
        globals()[module_name] = module
        __all__.append(module_name)
    except ImportError:
        pass

# Specific toolkit imports with fallback
_toolkits = [
    ('analysis.jira_analyse', 'AnalyseJira'),
    ('analysis.ado_analyse', 'AnalyseAdo'), 
    ('analysis.gitlab_analyse', 'AnalyseGitLab'),
    ('analysis.github_analyse', 'AnalyseGithub')
]

for module_path, class_name in _toolkits:
    try:
        module = importlib.import_module(f'.{module_path}', package=__name__)
        toolkit_class = getattr(module, class_name)
        globals()[class_name] = toolkit_class
        __all__.append(class_name)
    except (ImportError, AttributeError):
        pass

def get_toolkits():
    """Get all available community toolkits configurations."""
    toolkits = []
    
    for _, class_name in _toolkits:
        if class_name in globals():
            try:
                toolkits.append(globals()[class_name].toolkit_config_schema())
            except AttributeError:
                pass
    
    return toolkits

def get_tools(tools_list: list, alita_client, llm) -> list:
    """Get community tools based on the tools list configuration."""
    tools = []
    
    # Tool type to class mapping
    _tool_mapping = {
        'analyse_jira': 'AnalyseJira',
        'analyse_ado': 'AnalyseAdo',
        'analyse_gitlab': 'AnalyseGitLab', 
        'analyse_github': 'AnalyseGithub'
    }
    
    for tool in tools_list:
        tool_type = tool.get('type')
        class_name = _tool_mapping.get(tool_type)
        
        if class_name and class_name in globals():
            try:
                toolkit_class = globals()[class_name]
                toolkit = toolkit_class.get_toolkit(
                    client=alita_client,
                    **tool['settings']
                )
                tools.extend(toolkit.get_tools())
            except Exception:
                pass  # Fail silently for robustness
    
    return tools

# Export the functions
__all__.extend(["get_toolkits", "get_tools"])