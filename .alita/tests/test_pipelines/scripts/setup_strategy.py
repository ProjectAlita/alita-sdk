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
    
    def __init__(self, toolkit_configs: Optional[Dict[str, Any]] = None, llm: Optional[Any] = None):
        """
        Initialize local strategy.
        
        Args:
            toolkit_configs: Optional pre-loaded toolkit configurations
            llm: Optional pre-created LLM instance (for image processing, etc.)
        """
        self.toolkit_configs = toolkit_configs or {}
        self.created_toolkits: Dict[str, Any] = {}
        self.created_configurations: Dict[str, Any] = {}
        self.created_tools: List[Any] = []  # Store instantiated tools
        self._next_toolkit_id = 1
        self._alita_client = None
        self._llm = llm  # Use provided LLM or create on demand
        self._configuration_data: Dict[str, Dict[str, Any]] = {}  # Store configuration data by alita_title
    
    def get_tools(self) -> List[Any]:
        """
        Get the list of instantiated toolkit tools.
        
        Returns:
            List of BaseTool instances created during setup
        """
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[GET_TOOLS] Returning {len(self.created_tools)} tools")
        logger.info(f"[GET_TOOLS] Tool names: {[t.name if hasattr(t, 'name') else str(type(t)) for t in self.created_tools]}")
        return self.created_tools
    
    def create_fresh_toolkit_instance(self, toolkit_name: str, ctx: Optional["SetupContext"] = None) -> List[Any]:
        """
        Create a fresh toolkit instance with the same configuration.
        
        This method recreates toolkit tools from stored configuration,
        providing complete isolation for parallel test execution.
        
        Args:
            toolkit_name: Name of the toolkit to recreate
            ctx: Optional SetupContext for logging
            
        Returns:
            List of freshly created BaseTool instances
        """
        import logging
        logger = logging.getLogger(__name__)
        
        if toolkit_name not in self.created_toolkits:
            logger.warning(f"Toolkit '{toolkit_name}' not found in created_toolkits")
            return []
        
        toolkit_info = self.created_toolkits[toolkit_name]
        logger.info(f"Creating fresh instance of toolkit '{toolkit_name}' (type: {toolkit_info['type']})")
        
        # Create fresh tools using saved configuration
        # Note: ctx is optional for _create_toolkit_tools, only used for logging
        tools = self._create_toolkit_tools(toolkit_info, ctx)
        logger.info(f"Created {len(tools)} fresh tools for '{toolkit_name}'")
        
        return tools
    
    def get_toolkit_names(self) -> List[str]:
        """Get list of toolkit names that were created during setup."""
        return list(self.created_toolkits.keys())
    
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
        import logging
        logger = logging.getLogger(__name__)
        logger.info("[TOOLKIT CREATE] Entered _create_toolkit_tools()")
        
        from utils_common import load_from_env
        
        toolkit_type = toolkit_info.get("type", "unknown")
        toolkit_name = toolkit_info.get("name", "unknown")
        toolkit_id = toolkit_info.get("id", 1)
        config = toolkit_info.get("config", {})
        
        logger.info(f"[TOOLKIT CREATE] toolkit_type={toolkit_type}, toolkit_name={toolkit_name}, toolkit_id={toolkit_id}")
        
        # Initialize alita client if needed
        if self._alita_client is None:
            logger.info("[TOOLKIT CREATE] Creating AlitaClient")
            self._alita_client = self._create_alita_client()
            logger.info("[TOOLKIT CREATE] AlitaClient created")
        
        # Initialize LLM if needed (for toolkits that process images, etc.)
        if self._llm is None:
            logger.info("[TOOLKIT CREATE] Creating LLM")
            self._llm = self._create_llm()
            logger.info("[TOOLKIT CREATE] LLM created")
        
        # Build tool configuration in the format expected by get_tools
        # This matches the structure used by the backend
        logger.info("[TOOLKIT CREATE] Calling _build_toolkit_settings")
        settings = self._build_toolkit_settings(toolkit_type, config, load_from_env)
        logger.info(f"[TOOLKIT CREATE] _build_toolkit_settings completed, settings keys: {list(settings.keys())}")
        
        # DEBUG: Log the settings structure
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[LOCAL DEBUG] Built settings for {toolkit_type}: {list(settings.keys())}")
        config_key = f"{toolkit_type}_configuration"
        if config_key in settings:
            logger.info(f"[LOCAL DEBUG] {config_key} content: {settings[config_key]}")
        
        tool_config = {
            "id": toolkit_id,
            "type": toolkit_type,
            "toolkit_name": toolkit_name,
            "name": toolkit_name,
            "settings": settings,
        }
        
        logger.info(f"[LOCAL DEBUG] Final tool_config being passed to get_tools: {tool_config}")
        
        try:
            from alita_sdk.runtime.toolkits.tools import get_tools
            
            logger.info("[TOOLKIT CREATE] Calling get_tools from alita_sdk.runtime.toolkits.tools")
            tools = get_tools(
                tools_list=[tool_config],
                alita_client=self._alita_client,
                llm=self._llm,
                memory_store=None,
                debug_mode=False,
            )
            logger.info(f"[TOOLKIT CREATE] get_tools returned {len(tools)} tools")
            
            ctx.log(f"[LOCAL] Created {toolkit_type} toolkit '{toolkit_name}' with {len(tools)} tools", "success")
            return tools
            
        except Exception as e:
            logger.error(f"[TOOLKIT CREATE] Exception in get_tools: {e}", exc_info=True)
            ctx.log(f"[LOCAL] Failed to create {toolkit_type} toolkit: {e}", "error")
            return []
    
    def _build_toolkit_settings(self, toolkit_type: str, config: Dict[str, Any], load_from_env) -> Dict[str, Any]:
        """
        Build settings dict for a toolkit in the format expected by get_tools.
        
        This method mirrors the remote mode behavior - it takes already-resolved
        configuration (with all ${VAR} placeholders substituted via resolve_env_value)
        and structures it for toolkit creation.
        
        Logic:
        1. Start with existing {toolkit_type}_configuration from config if present
        2. If alita_title is present, merge in stored configuration data from configuration step
        3. All placeholders should already be resolved by resolve_env_value before this method
        4. Fill in any defaults from the Pydantic model if needed
        
        Args:
            toolkit_type: Type of toolkit (e.g., 'github', 'jira')
            config: Configuration dict with all ${VAR} placeholders already resolved
            load_from_env: Function to load values from .env file (for defaults only)
            
        Returns:
            Settings dict with {toolkit_type}_configuration populated
        """
        settings = config.copy()
        
        # Build the configuration key name (e.g., 'github_configuration', 'jira_configuration')
        # Special handling for toolkit types that don't match their configuration key
        toolkit_type = "ado" if toolkit_type.startswith("ado") else toolkit_type
        # xray_cloud uses xray_configuration, not xray_cloud_configuration
        if toolkit_type == "xray_cloud":
            config_key = "xray_configuration"
        else:
            config_key = f"{toolkit_type}_configuration"
        
        # Start with existing configuration from config dict if present
        existing_config = config.get(config_key, {})
        toolkit_config = existing_config.copy() if isinstance(existing_config, dict) else {}
        
        # DEBUG: Log config state before merge
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[MERGE DEBUG] toolkit_type: {toolkit_type}, config_key: {config_key}")
        logger.info(f"[MERGE DEBUG] toolkit_config: {toolkit_config}")
        logger.info(f"[MERGE DEBUG] _configuration_data keys: {list(self._configuration_data.keys())}")
        logger.info(f"[MERGE DEBUG] 'alita_title' in toolkit_config: {'alita_title' in toolkit_config}")
        if 'alita_title' in toolkit_config:
            logger.info(f"[MERGE DEBUG] toolkit_config['alita_title']: {toolkit_config['alita_title']}")
            logger.info(f"[MERGE DEBUG] alita_title in _configuration_data: {toolkit_config['alita_title'] in self._configuration_data}")
        
        # If toolkit_config has an alita_title, try to load stored configuration data
        if 'alita_title' in toolkit_config and toolkit_config['alita_title'] in self._configuration_data:
            stored_data = self._configuration_data[toolkit_config['alita_title']]
            # DEBUG: Log what we're merging
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"[LOCAL DEBUG] Found alita_title: {toolkit_config['alita_title']}")
            logger.info(f"[LOCAL DEBUG] Stored data keys: {list(stored_data.keys())}")
            logger.info(f"[LOCAL DEBUG] Stored data: {stored_data}")
            logger.info(f"[LOCAL DEBUG] toolkit_config BEFORE merge: {toolkit_config}")
            # Merge stored configuration data (credentials) into toolkit_config
            # When alita_title is present, stored data takes PRECEDENCE over config file values
            # This allows credentials to come from the configuration step while keeping
            # config file placeholders for remote mode compatibility
            for key, value in stored_data.items():
                # Skip alita_title and private fields - they're metadata, not credentials
                if key in ('alita_title', 'private'):
                    continue
                # Always overwrite with stored credentials when alita_title is used  
                toolkit_config[key] = value
                logger.info(f"[LOCAL DEBUG] Merged {key} into toolkit_config (overwrite)")
            logger.info(f"[LOCAL DEBUG] toolkit_config AFTER merge: {toolkit_config}")
        
        # Fill in defaults from Pydantic model if available
        try:
            from alita_sdk.configurations import get_class_configurations
            
            config_classes = get_class_configurations()
            
            if toolkit_type in config_classes:
                config_class = config_classes[toolkit_type]
                model_fields = config_class.model_fields
                
                for field_name, field_info in model_fields.items():
                    # Only set default if field is completely missing
                    if field_name not in toolkit_config or toolkit_config[field_name] is None:
                        if field_info.default is not None:
                            toolkit_config[field_name] = field_info.default
        
        except Exception as e:
            # If configuration class not available, just use what we have
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
    
    def _create_llm(self) -> Optional[Any]:
        from utils_common import load_from_env
        """Create LLM instance for toolkits that need it (e.g., image processing)."""
        if self._alita_client is None:
            return None
        
        try:
            llm = self._alita_client.get_llm(
                model_name=load_from_env('DEFAULT_LLM_MODEL') or 'gpt-5-mini',
                model_config={
                    'temperature': 0.0,
                    'max_tokens': 4096,
                }
            )
            return llm
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
                file_config = load_toolkit_config(
                    config["config_file"], 
                    base_path,
                    env_substitutions=ctx.env_vars,
                    env_loader=load_from_env
                )
            except FileNotFoundError:
                ctx.log(f"Config file not found: {config['config_file']}", "warning")
        
        # Apply overrides - resolve environment variables in overrides first
        overrides = resolve_env_value(config.get("overrides", {}), ctx.env_vars, env_loader=load_from_env)
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
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[TOOLKIT CREATE] Calling _create_toolkit_tools for {toolkit_name}")
        try:
            tools = self._create_toolkit_tools(toolkit_info, ctx)
            logger.info(f"[TOOLKIT CREATE] _create_toolkit_tools returned {len(tools)} tools")
        except Exception as e:
            logger.error(f"[TOOLKIT CREATE] Exception in _create_toolkit_tools: {e}", exc_info=True)
            tools = []
        logger.info(f"[TOOLKIT CREATE] created_tools BEFORE extend: {len(self.created_tools)}")
        self.created_tools.extend(tools)
        logger.info(f"[TOOLKIT CREATE] created_tools AFTER extend: {len(self.created_tools)}")
        
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
        Handle toolkit invocation locally by executing the tool directly.
        
        Finds the matching tool from self.created_tools and invokes it
        with the specified parameters.
        """
        from utils_common import resolve_env_value, load_from_env
        
        config = resolve_env_value(step.get("config", {}), ctx.env_vars, env_loader=load_from_env)
        
        toolkit_id = config.get("toolkit_id") or config.get("toolkit_ref")
        tool_name = config.get("tool_name")
        tool_params = resolve_env_value(config.get("tool_params", {}), ctx.env_vars, env_loader=load_from_env)
        
        if not toolkit_id:
            ctx.log("[LOCAL] No toolkit_id provided, skipping", "warning")
            return {"success": True, "skipped": True, "reason": "no toolkit_id", "local": True}
        
        if not tool_name:
            ctx.log("[LOCAL] No tool_name provided, skipping", "warning")
            return {"success": True, "skipped": True, "reason": "no tool_name", "local": True}
        
        ctx.log(f"[LOCAL] Invoking toolkit tool: {tool_name} with params: {tool_params}")
        
        # Find the matching tool from created tools
        matching_tool = None
        for tool in self.created_tools:
            if hasattr(tool, 'name') and tool.name == tool_name:
                matching_tool = tool
                break
        
        if not matching_tool:
            ctx.log(f"[LOCAL] Tool '{tool_name}' not found in created tools", "error")
            available_tools = [t.name for t in self.created_tools if hasattr(t, 'name')]
            ctx.log(f"[LOCAL] Available tools: {available_tools}", "info")
            return {
                "success": False,
                "error": f"Tool '{tool_name}' not found",
                "available_tools": available_tools,
                "local": True
            }
        
        # Execute the tool
        try:
            ctx.log(f"[LOCAL] Executing tool: {tool_name}", "info")
            result = matching_tool.invoke(tool_params)
            ctx.log(f"[LOCAL] Tool {tool_name} executed successfully", "success")
            
            return {
                "success": True,
                "result": result,
                "local": True
            }
        except Exception as e:
            ctx.log(f"[LOCAL] Tool {tool_name} execution failed: {e}", "error")
            return {
                "success": False,
                "error": str(e),
                "local": True
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
        
        # DEBUG: Log configuration data
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[CONFIG DEBUG] config_type: {config_type}")
        logger.info(f"[CONFIG DEBUG] alita_title: {alita_title}")
        logger.info(f"[CONFIG DEBUG] data keys: {list(data.keys())}")
        logger.info(f"[CONFIG DEBUG] data content: {data}")
        
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
        
        # Also store the data for lookup by alita_title
        self._configuration_data[alita_title] = data
        
        # DEBUG: Verify storage
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[CONFIG DEBUG] Stored in _configuration_data['{alita_title}']: {self._configuration_data[alita_title]}")
        
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
