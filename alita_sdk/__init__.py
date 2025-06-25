"""
Alita SDK - A unified SDK for building langchain agents using resources from Alita.

This package contains three main modules:
- runtime: Core runtime functionality for agents, clients, and language models
- tools: Collection of tools for various integrations and services  
- community: Community extensions and utilities
"""

__version__ = "0.3.142"

__all__ = ["runtime", "tools", "community"]

import importlib

def __getattr__(name):
    if name in __all__:
        module = importlib.import_module(f".{name}", __name__)
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__} has no attribute {name}")
