"""
Alita SDK Community Module

This module contains community extensions and utilities for the Alita SDK.
Includes analysis tools, browser automation, research tools, and exploratory data analysis.
"""

import importlib
import logging

logger = logging.getLogger(__name__)

# Import available community modules
__all__ = []

# Standard module imports with fallback
_modules = ['utils', 'analysis', 'deep_researcher', 'eda', 'inventory']

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
    ('analysis.github_analyse', 'AnalyseGithub'),
    ('inventory.toolkit', 'InventoryToolkit')
]

for module_path, class_name in _toolkits:
    try:
        module = importlib.import_module(f'.{module_path}', package=__name__)
        toolkit_class = getattr(module, class_name)
        globals()[class_name] = toolkit_class
        __all__.append(class_name)
    except (ImportError, AttributeError):
        pass


def _register_community_toolkits():
    """Register community toolkits into the central tools registry."""
    try:
        from alita_sdk.tools import AVAILABLE_TOOLS, AVAILABLE_TOOLKITS, FAILED_IMPORTS
    except ImportError:
        logger.debug("Could not import tools registry, skipping community toolkit registration")
        return
    
    # Community toolkit definitions: (tool_name, module_path, get_tools_func_name, toolkit_class_name)
    _community_toolkit_defs = [
        ('inventory', 'inventory', 'get_tools', 'InventoryRetrievalToolkit'),
    ]
    
    for tool_name, module_path, get_tools_name, toolkit_class_name in _community_toolkit_defs:
        try:
            module = importlib.import_module(f'.{module_path}', package=__name__)
            
            imported = {}
            if get_tools_name and hasattr(module, get_tools_name):
                imported['get_tools'] = getattr(module, get_tools_name)
            
            if toolkit_class_name and hasattr(module, toolkit_class_name):
                imported['toolkit_class'] = getattr(module, toolkit_class_name)
                AVAILABLE_TOOLKITS[toolkit_class_name] = getattr(module, toolkit_class_name)
            
            if imported:
                AVAILABLE_TOOLS[tool_name] = imported
                logger.debug(f"Successfully registered community toolkit: {tool_name}")
        
        except Exception as e:
            FAILED_IMPORTS[tool_name] = str(e)
            logger.debug(f"Failed to register community toolkit {tool_name}: {e}")


# Register community toolkits on module import
_register_community_toolkits()

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
        'analyse_github': 'AnalyseGithub',
        'inventory': 'InventoryToolkit'
    }

    for tool in tools_list:
        if isinstance(tool, dict):
            tool_type = tool.get('type')
        else:
            logger.error(f"Community tools received non-dict tool: {tool} (type: {type(tool)})")
            continue
        class_name = _tool_mapping.get(tool_type)
        
        if class_name and class_name in globals():
            try:
                toolkit_class = globals()[class_name]
                
                # Special handling for inventory toolkit - pass sibling configs
                if tool_type == 'inventory':
                    from .inventory import get_tools as inventory_get_tools
                    # inventory_get_tools returns a list of tools directly
                    inventory_tools = inventory_get_tools(tool, tools_list=tools_list)
                    # Inject alita and llm into api_wrapper for each tool
                    for t in inventory_tools:
                        if hasattr(t, 'api_wrapper'):
                            t.api_wrapper.alita = alita_client
                            t.api_wrapper.llm = llm
                    tools.extend(inventory_tools)
                else:
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