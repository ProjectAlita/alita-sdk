"""
Alita SDK Runtime Module

This module contains the core runtime functionality for building langchain agents.
Includes agents, clients, language models, and utilities.
"""

import importlib

# Import available runtime modules
__all__ = []

# Standard imports with fallback
_modules = ['agents', 'clients', 'langchain', 'llamaindex', 'llms', 'toolkits', 'tools', 'utils']

for module_name in _modules:
    try:
        module = importlib.import_module(f'.{module_name}', package=__name__)
        globals()[module_name] = module
        __all__.append(module_name)
    except ImportError:
        pass

# Always try to export core functions from toolkits
try:
    from .toolkits.tools import get_tools, get_toolkits
    __all__.extend(["get_tools", "get_toolkits"])
except ImportError:
    pass