"""
Alita SDK Runtime Module

This module contains the core runtime functionality for building langchain agents.
Includes agents, clients, language models, and utilities.
"""

import importlib

_modules = [
    "agents",
    "clients",
    "langchain",
    "llamaindex",
    "llms",
    "toolkits",
    "tools",
    "utils",
]

__all__ = _modules + ["get_tools", "get_toolkits"]

def __getattr__(name):
    if name in _modules:
        module = importlib.import_module(f".{name}", __name__)
        globals()[name] = module
        return module
    if name in {"get_tools", "get_toolkits"}:
        toolkits = importlib.import_module(".toolkits.tools", __name__)
        value = getattr(toolkits, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__} has no attribute {name}")
