"""
Toolkit utilities for instantiating and managing toolkits.
This module provides toolkit management functions that are not tied to any specific interface.
"""

import logging
import random
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


def instantiate_toolkit_with_client(toolkit_config: Dict[str, Any], 
                                   llm_client: Any, 
                                   alita_client: Optional[Any] = None) -> List[Any]:
    """
    Instantiate a toolkit with LLM client support.
    
    This is a variant of instantiate_toolkit that includes LLM client support
    for toolkits that require LLM capabilities.
    
    Args:
        toolkit_config: Configuration dictionary for the toolkit
        llm_client: LLM client instance for tools that need LLM capabilities
        client: Optional additional client instance
    
    Returns:
        List of instantiated tools from the toolkit
        
    Raises:
        ValueError: If required configuration or client is missing
        Exception: If toolkit instantiation fails
    """
    try:
        from ..toolkits.tools import get_tools
        
        toolkit_name = toolkit_config.get('toolkit_name')
        if not toolkit_name:
            raise ValueError("toolkit_name is required in configuration")
        
        if not llm_client:
            raise ValueError("LLM client is required but not provided")
        
        settings = toolkit_config.get('settings', {})
        
        # Log the configuration being used
        logger.info(f"Instantiating toolkit {toolkit_name} with LLM client")
        logger.debug(f"Toolkit {toolkit_name} configuration: {toolkit_config}")
        
        # Create a tool configuration dict with required fields
        tool_config = {
            'id': toolkit_config.get('id', random.randint(1, 1000000)),
            'type': toolkit_config.get('type', toolkit_name.lower()),
            'settings': settings,
            'toolkit_name': toolkit_name
        }
        
        # Get tools using the toolkit configuration with clients
        # Parameter order: get_tools(tools_list, alita_client, llm, memory_store)
        tools = get_tools([tool_config], alita_client, llm_client)
        
        if not tools:
            logger.warning(f"No tools returned for toolkit {toolkit_name}")
            return []
        
        logger.info(f"Successfully instantiated toolkit {toolkit_name} with {len(tools)} tools")
        return tools
            
    except Exception as e:
        logger.error(f"Error instantiating toolkit {toolkit_name} with client: {str(e)}")
        raise


def get_toolkit_tools(toolkit_instance: Any) -> List[Any]:
    """
    Extract tools from an instantiated toolkit instance.
    
    This function provides a standardized way to get tools from various
    toolkit implementations that might have different interfaces.
    
    Args:
        toolkit_instance: An instantiated toolkit object
        
    Returns:
        List of tools from the toolkit
        
    Raises:
        ValueError: If no tools can be extracted from the toolkit
    """
    try:
        # Try different methods to get tools from the toolkit
        if hasattr(toolkit_instance, 'get_tools'):
            tools = toolkit_instance.get_tools()
        elif hasattr(toolkit_instance, 'tools'):
            tools = toolkit_instance.tools
        elif hasattr(toolkit_instance, '_tools'):
            tools = toolkit_instance._tools
        else:
            raise ValueError("Could not find tools in the toolkit instance")
        
        if not tools:
            logger.warning("Toolkit instance returned empty tools list")
            return []
        
        logger.info(f"Extracted {len(tools)} tools from toolkit instance")
        return tools
        
    except Exception as e:
        logger.error(f"Error extracting tools from toolkit: {str(e)}")
        raise


def find_tool_by_name(tools: List[Any], tool_name: str) -> Optional[Any]:
    """
    Find a specific tool by name from a list of tools.
    
    Args:
        tools: List of tool instances
        tool_name: Name of the tool to find
        
    Returns:
        The tool instance if found, None otherwise
    """
    for tool in tools:
        # Check various attributes that might contain the tool name
        if hasattr(tool, 'name') and tool.name == tool_name:
            return tool
        elif hasattr(tool, 'func') and hasattr(tool.func, '__name__') and tool.func.__name__ == tool_name:
            return tool
        elif hasattr(tool, '__name__') and tool.__name__ == tool_name:
            return tool
    
    return None


def get_tool_names(tools: List[Any]) -> List[str]:
    """
    Extract tool names from a list of tools.
    
    Args:
        tools: List of tool instances
        
    Returns:
        List of tool names
    """
    tool_names = []
    for tool in tools:
        if hasattr(tool, 'name'):
            tool_names.append(tool.name)
        elif hasattr(tool, 'func') and hasattr(tool.func, '__name__'):
            tool_names.append(tool.func.__name__)
        elif hasattr(tool, '__name__'):
            tool_names.append(tool.__name__)
        else:
            tool_names.append(str(tool))
    
    return tool_names
