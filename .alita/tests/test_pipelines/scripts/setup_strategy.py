#!/usr/bin/env python3
"""
Setup Strategy Pattern Implementation.

This module defines the Strategy pattern for executing setup steps.
Different strategies can be used for remote (backend) vs local execution.

Classes:
    SetupStrategy: Abstract base class defining the strategy interface
    RemoteSetupStrategy: Executes setup steps via remote backend API calls
    LocalSetupStrategy: Executes setup steps locally (for isolated testing)
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from setup import SetupContext


class SetupStrategy(ABC):
    """
    Abstract base class for setup execution strategies.
    
    Defines the interface for handling different step types during setup.
    Implementations can execute steps remotely (via API) or locally.
    """
    
    @abstractmethod
    def handle_toolkit_create(
        self,
        step: Dict[str, Any],
        ctx: "SetupContext",
        base_path: Path
    ) -> Dict[str, Any]:
        """
        Handle toolkit creation or update step.
        
        Args:
            step: Step configuration dict
            ctx: Setup context with environment and auth info
            base_path: Base path for resolving relative file paths
            
        Returns:
            Dict with 'success' key and optional 'id', 'name', 'error' keys
        """
        pass
    
    @abstractmethod
    def handle_toolkit_invoke(
        self,
        step: Dict[str, Any],
        ctx: "SetupContext"
    ) -> Dict[str, Any]:
        """
        Handle toolkit tool invocation step.
        
        Args:
            step: Step configuration dict
            ctx: Setup context with environment and auth info
            
        Returns:
            Dict with 'success' key and optional 'result', 'error' keys
        """
        pass
    
    @abstractmethod
    def handle_configuration(
        self,
        step: Dict[str, Any],
        ctx: "SetupContext"
    ) -> Dict[str, Any]:
        """
        Handle configuration creation/update step.
        
        Args:
            step: Step configuration dict
            ctx: Setup context with environment and auth info
            
        Returns:
            Dict with 'success' key and optional 'error' keys
        """
        pass


class RemoteSetupStrategy(SetupStrategy):
    """
    Remote setup strategy - executes steps via backend API calls.
    
    This is the default strategy that delegates to existing handler functions
    which make HTTP requests to the Elitea platform.
    """
    
    def handle_toolkit_create(
        self,
        step: Dict[str, Any],
        ctx: "SetupContext",
        base_path: Path
    ) -> Dict[str, Any]:
        """Execute toolkit creation via remote API."""
        # Import here to avoid circular imports
        from setup import handle_toolkit_create as remote_handle_toolkit_create
        return remote_handle_toolkit_create(step, ctx, base_path)
    
    def handle_toolkit_invoke(
        self,
        step: Dict[str, Any],
        ctx: "SetupContext"
    ) -> Dict[str, Any]:
        """Execute toolkit invocation via remote API."""
        from setup import handle_toolkit_invoke as remote_handle_toolkit_invoke
        return remote_handle_toolkit_invoke(step, ctx)
    
    def handle_configuration(
        self,
        step: Dict[str, Any],
        ctx: "SetupContext"
    ) -> Dict[str, Any]:
        """Execute configuration creation via remote API."""
        from setup import handle_configuration as remote_handle_configuration
        return remote_handle_configuration(step, ctx)


class LocalSetupStrategy(SetupStrategy):
    """
    Local setup strategy - executes steps locally without backend.
    
    This strategy is used for isolated testing where we don't want to
    interact with the remote backend. Instead, it creates local
    representations of toolkits and configurations, and instantiates
    actual toolkit tools for test execution.
    """
    
    def __init__(self, toolkit_configs: Optional[Dict[str, Any]] = None):
        """
        Initialize local strategy.
        
        Args:
            toolkit_configs: Optional pre-loaded toolkit configurations
        """
        self.toolkit_configs = toolkit_configs or {}
        self.created_toolkits: Dict[str, Any] = {}
        self.created_configurations: Dict[str, Any] = {}
        self.created_tools: List[Any] = []  # Store instantiated tools
        self._next_toolkit_id = 1
        self._alita_client = None
    
    def get_tools(self) -> List[Any]:
        """
        Get the list of instantiated toolkit tools.
        
        Returns:
            List of BaseTool instances created during setup
        """
        return self.created_tools
    
    def _create_toolkit_tools(self, toolkit_info: Dict[str, Any], ctx: "SetupContext") -> List[Any]:
        """
        Create actual toolkit tool instances from toolkit configuration.
        
        Uses get_tools from alita_sdk.runtime.toolkits.tools for consistent
        tool creation with the backend.
        
        Args:
            toolkit_info: Toolkit info dict with 'type', 'name', 'config'
            ctx: SetupContext for logging
            
        Returns:
            List of BaseTool instances
        """
        from utils_common import load_from_env
        
        toolkit_type = toolkit_info.get("type", "unknown")
        toolkit_name = toolkit_info.get("name", "unknown")
        toolkit_id = toolkit_info.get("id", 1)
        config = toolkit_info.get("config", {})
        
        # Initialize alita client if needed
        if self._alita_client is None:
            self._alita_client = self._create_alita_client()
        
        # Import DEFAULT_LLM_SETTINGS from seed_pipelines
        from seed_pipelines import DEFAULT_LLM_SETTINGS
        
        # Create LLM with settings from DEFAULT_LLM_SETTINGS
        llm_model_name = DEFAULT_LLM_SETTINGS.get("model_name", "gpt-4o-2024-11-20")
        llm_config = {
            "max_tokens": DEFAULT_LLM_SETTINGS.get("max_tokens", 4096),
            "temperature": DEFAULT_LLM_SETTINGS.get("temperature", 0.5),
        }
        llm = self._alita_client.get_llm(llm_model_name, model_config=llm_config)
        
        # Build tool configuration in the format expected by get_tools
        # This matches the structure used by the backend
        tool_config = {
            "id": toolkit_id,
            "type": toolkit_type,
            "toolkit_name": toolkit_name,
            "name": toolkit_name,
            "settings": self._build_toolkit_settings(toolkit_type, config, load_from_env),
        }
        
        try:
            from alita_sdk.runtime.toolkits.tools import get_tools
            
            tools = get_tools(
                tools_list=[tool_config],
                alita_client=self._alita_client,
                llm=llm,
                memory_store=None,
                debug_mode=False,
            )
            
            ctx.log(f"[LOCAL] Created {toolkit_type} toolkit '{toolkit_name}' with {len(tools)} tools", "success")
            return tools
            
        except Exception as e:
            ctx.log(f"[LOCAL] Failed to create {toolkit_type} toolkit: {e}", "error")
            return []
    
    def _build_toolkit_settings(self, toolkit_type: str, config: Dict[str, Any], load_from_env) -> Dict[str, Any]:
        """
        Build settings dict for a toolkit in the format expected by get_tools.
        
        Uses configuration schemas from alita_sdk.configurations to dynamically
        determine required fields and load values from environment variables.
        
        Logic:
        1. Get configuration class for toolkit_type from alita_sdk.configurations
        2. Extract all field names from the Pydantic model
        3. For each field, try to load value from:
           a. Provided config dict
           b. Environment variable: {TOOLKIT_TYPE}_{FIELD_NAME} (uppercase)
        4. Build {toolkit_type}_configuration dict with all values
        
        Args:
            toolkit_type: Type of toolkit (e.g., 'github', 'jira')
            config: Base configuration dict (may contain some values)
            load_from_env: Function to load values from .env file
            
        Returns:
            Settings dict with {toolkit_type}_configuration populated
        """
        settings = config.copy()
        
        # Build the configuration key name (e.g., 'github_configuration', 'jira_configuration')
        config_key = f"{toolkit_type}_configuration"
        
        # Always start with fresh configuration (override any existing)
        toolkit_config = {}
        
        try:
            # Import configuration classes dynamically
            from alita_sdk.configurations import get_class_configurations
            
            config_classes = get_class_configurations()
            
            if toolkit_type in config_classes:
                config_class = config_classes[toolkit_type]
                
                # Extract field information from Pydantic model
                model_fields = config_class.model_fields
                
                for field_name, field_info in model_fields.items():
                    # Try to get value from config dict first
                    value = config.get(field_name)
                    
                    # If not in config, try environment variable
                    # Pattern: {TOOLKIT_TYPE}_{FIELD_NAME} (uppercase)
                    if not value:
                        env_var_name = f"{toolkit_type.upper()}_{field_name.upper()}"
                        value = load_from_env(env_var_name)
                    # Set the value if found
                    if value:
                        toolkit_config[field_name] = value
                    elif field_info.default is not None:
                        # Use default value from model if available
                        toolkit_config[field_name] = field_info.default
        
        except Exception as e:
            # If configuration class not available, fall back to basic approach
            # Just use values from config dict
            pass
        
        # Store the configuration in settings
        settings[config_key] = toolkit_config
        
        return settings
    
    def _create_alita_client(self) -> Optional[Any]:
        """Create AlitaClient for toolkit initialization."""
        from utils_common import load_from_env
        
        try:
            from alita_sdk.runtime.clients.client import AlitaClient
            
            deployment_url = load_from_env('DEPLOYMENT_URL') or load_from_env('BASE_URL')
            api_key = load_from_env('API_KEY') or load_from_env('AUTH_TOKEN')
            project_id = load_from_env('PROJECT_ID')
            
            if not deployment_url or not api_key:
                return None
            
            return AlitaClient(
                base_url=deployment_url,
                auth_token=api_key,
                project_id=int(project_id) if project_id else 0,
            )
        except Exception:
            return None
    
    def handle_toolkit_create(
        self,
        step: Dict[str, Any],
        ctx: "SetupContext",
        base_path: Path
    ) -> Dict[str, Any]:
        """
        Handle toolkit creation locally.
        
        Creates a local representation of the toolkit without calling backend.
        Assigns a local ID, stores the configuration, and instantiates actual tools.
        """
        from utils_common import resolve_env_value, load_from_env, load_toolkit_config
        
        config = resolve_env_value(step.get("config", {}), ctx.env_vars, env_loader=load_from_env)
        
        # Load base config from file if specified
        file_config = {}
        if "config_file" in config:
            try:
                file_config = load_toolkit_config(config["config_file"], base_path)
            except FileNotFoundError:
                ctx.log(f"Config file not found: {config['config_file']}", "warning")
        
        # Apply overrides
        overrides = config.get("overrides", {})
        for key, value in overrides.items():
            if isinstance(value, dict) and key in file_config and isinstance(file_config[key], dict):
                file_config[key].update(value)
            else:
                file_config[key] = value
        
        toolkit_name = config.get("toolkit_name", file_config.get("toolkit_name", "local_toolkit"))
        toolkit_type = config.get("toolkit_type", file_config.get("type", "unknown"))
        
        # Generate local ID
        toolkit_id = self._next_toolkit_id
        self._next_toolkit_id += 1
        
        # Store toolkit info locally
        toolkit_info = {
            "id": toolkit_id,
            "name": toolkit_name,
            "type": toolkit_type,
            "config": file_config,
        }
        self.created_toolkits[toolkit_name] = toolkit_info
        
        ctx.log(f"[LOCAL] Registered toolkit '{toolkit_name}' (type: {toolkit_type}) with ID {toolkit_id}", "success")
        
        # Create actual tool instances
        tools = self._create_toolkit_tools(toolkit_info, ctx)
        self.created_tools.extend(tools)
        
        return {
            "success": True,
            "id": toolkit_id,
            "name": toolkit_name,
            "tools_count": len(tools),
            "local": True,
        }
    
    def handle_toolkit_invoke(
        self,
        step: Dict[str, Any],
        ctx: "SetupContext"
    ) -> Dict[str, Any]:
        """
        Handle toolkit invocation locally.
        
        For local execution, we skip actual tool invocation and return
        a placeholder success result. Real tool execution happens during
        test execution, not setup.
        """
        from utils_common import resolve_env_value, load_from_env
        
        config = resolve_env_value(step.get("config", {}), ctx.env_vars, env_loader=load_from_env)
        
        toolkit_id = config.get("toolkit_id") or config.get("toolkit_ref")
        tool_name = config.get("tool_name")
        
        if not toolkit_id:
            ctx.log("[LOCAL] No toolkit_id provided, skipping", "warning")
            return {"success": True, "skipped": True, "reason": "no toolkit_id", "local": True}
        
        if not tool_name:
            ctx.log("[LOCAL] No tool_name provided, skipping", "warning")
            return {"success": True, "skipped": True, "reason": "no tool_name", "local": True}
        
        ctx.log(f"[LOCAL] Skipping toolkit invoke: {tool_name} (local mode)", "info")
        
        return {
            "success": True,
            "skipped": True,
            "reason": "local_mode",
            "local": True,
            "result": {},
        }
    
    def handle_configuration(
        self,
        step: Dict[str, Any],
        ctx: "SetupContext"
    ) -> Dict[str, Any]:
        """
        Handle configuration creation locally.
        
        Creates a local representation of the configuration.
        Actual credentials should be loaded from environment/.env file.
        """
        from utils_common import resolve_env_value, load_from_env
        
        config = resolve_env_value(step.get("config", {}), ctx.env_vars, env_loader=load_from_env)
        
        config_type = config.get("config_type")
        alita_title = config.get("alita_title")
        data = config.get("data", {})
        
        if not config_type:
            ctx.log("[LOCAL] No config_type provided", "warning")
            return {"success": True, "skipped": True, "reason": "no config_type", "local": True}
        
        if not alita_title:
            ctx.log("[LOCAL] No alita_title provided", "warning")
            return {"success": True, "skipped": True, "reason": "no alita_title", "local": True}
        
        # Store locally - credentials come from env
        self.created_configurations[alita_title] = {
            "type": config_type,
            "title": alita_title,
            "data": data,
        }
        
        ctx.log(f"[LOCAL] Registered configuration '{alita_title}' of type '{config_type}'", "success")
        
        return {
            "success": True,
            "local": True,
            "config_type": config_type,
            "title": alita_title,
        }


# Default strategy instance for convenience
_default_strategy: Optional[SetupStrategy] = None


def get_default_strategy() -> SetupStrategy:
    """Get the default setup strategy (RemoteSetupStrategy)."""
    global _default_strategy
    if _default_strategy is None:
        _default_strategy = RemoteSetupStrategy()
    return _default_strategy


def set_default_strategy(strategy: SetupStrategy):
    """Set the default setup strategy."""
    global _default_strategy
    _default_strategy = strategy
