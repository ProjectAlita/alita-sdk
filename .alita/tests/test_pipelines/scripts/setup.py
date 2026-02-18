#!/usr/bin/env python3
"""
Execute setup steps from a test suite's pipeline config.

This script reads the setup configuration and prepares the environment
for running tests. It is toolkit-agnostic - all toolkit-specific configuration
comes from the config.yaml file, not hardcoded in this script.

Supported step types:
  - toolkit: Create or update toolkit entities on the platform
  - toolkit_invoke: Invoke any tool from any toolkit
  - configuration: Create or ensure configurations exist (credentials, etc.)

Usage:
    python setup.py <suite_folder> [options]
    python setup.py <suite_folder>:<pipeline_file.yaml> [options]

Examples:
    python setup.py github_toolkit
    python setup.py github_toolkit_negative:pipeline_validation.yaml
    python setup.py github_toolkit --dry-run
    python setup.py github_toolkit -v

Suite Specification Format:
    - 'suite_name' - Uses default pipeline.yaml in the suite folder
    - 'suite_name:pipeline_file.yaml' - Uses specific pipeline config file
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import requests
import yaml

# Force UTF-8 encoding for Windows compatibility
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    pass  # Python < 3.7
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

from seed_pipelines import (
    DEFAULT_BASE_URL,
    DEFAULT_PROJECT_ID,
)

# Import shared utilities
from utils_common import (
    load_config,
    load_toolkit_config,
    parse_suite_spec,
    resolve_env_value,
    set_env_file,
    load_from_env,
    load_token_from_env,
    load_base_url_from_env,
    load_project_id_from_env,
)

from logger import TestLogger


class SetupContext:
    """Context for setup execution, holds state and environment."""

    def __init__(
        self,
        base_url: str,
        project_id: int,
        bearer_token: str,
        verbose: bool = False,
        dry_run: bool = False,
        logger: TestLogger = None,
    ):
        self.base_url = base_url
        self.project_id = project_id
        self.bearer_token = bearer_token
        self.verbose = verbose
        self.dry_run = dry_run
        self.env_vars: dict[str, Any] = {}
        self.created_resources: list[dict] = []
        self.logger = logger

        # Add timestamp for unique naming
        self.env_vars["TIMESTAMP"] = datetime.now().strftime("%Y%m%d-%H%M%S")

    def get_headers(self, content_type: bool = False) -> dict:
        """Get HTTP headers with authentication."""
        headers = {"Authorization": f"Bearer {self.bearer_token}"}
        if content_type:
            headers["Content-Type"] = "application/json"
        return headers

    def log(self, message: str, level: str = "info"):
        """Log a message using the unified logger or fallback to print."""
        if self.logger:
            if level == "success":
                self.logger.success(message)
            elif level == "error":
                self.logger.error(message)
            elif level == "warning":
                self.logger.warning(message)
            else:  # info
                self.logger.info(message)
        elif self.verbose:
            prefix = {"info": "  ", "success": "  ✓", "error": "  ✗", "warning": "  ⚠"}
            print(f"{prefix.get(level, '  ')} {message}")

    def save_env(self, key: str, value: Any):
        """Save a value to the context environment."""
        self.env_vars[key] = value
        self.log(f"Saved {key}={value}", "info")


def extract_json_path(data: Any, path: str) -> Any:
    """
    Extract a value from data using a simple JSON path ($.field.subfield or $.array[0].field).
    
    Supports:
    - $.field.subfield - nested dict access
    - $.array[0] - array indexing
    - $.array[0].field - combined array and dict access
    """
    import re
    
    if not path.startswith("$."):
        return path

    # Remove leading $. 
    path = path[2:]
    
    # Parse path handling both dot notation and bracket notation
    # Split on dots but preserve bracketed indices
    parts = []
    current = ""
    for char in path:
        if char == '.':
            if current:
                parts.append(current)
                current = ""
        else:
            current += char
    if current:
        parts.append(current)
    
    result = data
    for part in parts:
        if result is None:
            return None
            
        # Check for bracket notation (e.g., "issues[0]")
        bracket_match = re.match(r'^([^\[]+)\[(\d+)\]$', part)
        if bracket_match:
            field_name = bracket_match.group(1)
            index = int(bracket_match.group(2))
            
            # First access the field
            if isinstance(result, dict):
                result = result.get(field_name)
            else:
                return None
            
            # Then index into the array
            if isinstance(result, list) and 0 <= index < len(result):
                result = result[index]
            else:
                return None
        elif isinstance(result, dict):
            result = result.get(part)
        elif isinstance(result, list) and part.isdigit():
            index = int(part)
            if 0 <= index < len(result):
                result = result[index]
            else:
                return None
        else:
            return None
            
    return result


def extract_regex_match(data: str, pattern: str, match_index: int = 0, group_index: int = 1) -> Any:
    """
    Extract a value from string data using regex pattern matching.
    
    Supports extracting the N-th match and specific capture groups.
    
    Args:
        data: String data to search in
        pattern: Regex pattern with capture groups
        match_index: Which match to extract (0 = first match, 1 = second match, etc.)
        group_index: Which capture group to extract from the match (1 = first group, etc.)
    
    Returns:
        The extracted value or None if not found
        
    Examples:
        # Extract first issue key: 'key': 'EL-455'
        extract_regex_match(data, r"'key': '([A-Z]+-\\d+)'", match_index=0, group_index=1)
        
        # Extract second issue key
        extract_regex_match(data, r"'key': '([A-Z]+-\\d+)'", match_index=1, group_index=1)
    """
    if not isinstance(data, str):
        return None
    
    try:
        matches = re.findall(pattern, data)
        if match_index < len(matches):
            match_result = matches[match_index]
            # If regex has groups, match_result is a tuple
            if isinstance(match_result, tuple):
                if group_index - 1 < len(match_result):
                    return match_result[group_index - 1]
            else:
                # Single group returns string directly
                if group_index == 1:
                    return match_result
        return None
    except Exception as e:
        return None


# =============================================================================
# Setup Step Handlers
# =============================================================================


def handle_toolkit_create(step: dict, ctx: SetupContext, base_path: Path) -> dict:
    """
    Handle toolkit creation or update.

    This is toolkit-agnostic - it creates any type of toolkit based on
    the configuration provided. Configuration can come from:
      - config_file: A JSON file with toolkit settings
      - overrides: Inline overrides to apply on top of file config
      - Direct config fields like toolkit_name, toolkit_type, settings

    Configuration management (credentials) should be handled as separate
    'configuration' steps before toolkit creation.
    """
    config = resolve_env_value(step.get("config", {}), ctx.env_vars, env_loader=load_from_env)

    # Load base config from file if specified
    file_config = {}
    if "config_file" in config:
        file_config = load_toolkit_config(
            config["config_file"],
            base_path,
            env_substitutions=ctx.env_vars,
            env_loader=load_from_env
        )

    # Apply overrides to file config
    overrides = config.get("overrides", {})
    for key, value in overrides.items():
        if isinstance(value, dict) and key in file_config and isinstance(file_config[key], dict):
            file_config[key].update(value)
        else:
            file_config[key] = value

    # Extract top-level fields
    toolkit_name = config.get("toolkit_name", file_config.get("toolkit_name", file_config.get("name", "test-toolkit")))
    toolkit_type = config.get("toolkit_type", file_config.get("type"))
    
    # Validate required fields
    if not toolkit_type:
        return {"success": False, "error": "toolkit_type is required in config or file_config"}

    # Build settings from file config (exclude top-level metadata fields)
    metadata_fields = {"type", "name", "toolkit_name"}
    settings = {k: v for k, v in file_config.items() if k not in metadata_fields}

    # Allow direct settings override from config
    if "settings" in config:
        settings.update(config["settings"])

    # Ensure user has an API token for synchronous tool invocation
    ctx.log("Ensuring user API token exists...")
    token_result = ensure_user_token(ctx, "api")
    if not token_result.get("success"):
        return {"success": False, "error": f"Failed to ensure user API token: {token_result.get('error')}"}

    toolkit_config = {
        "type": toolkit_type,
        "name": toolkit_name,
        "toolkit_name": toolkit_name,
        "settings": settings,
    }

    ctx.log(f"Creating toolkit: {toolkit_name} (type: {toolkit_type})")

    if ctx.dry_run:
        ctx.log(f"[DRY RUN] Would create toolkit with config: {json.dumps(toolkit_config, indent=2)[:200]}...")
        return {"success": True, "dry_run": True, "id": 0, "name": toolkit_name}

    # Check if toolkit exists
    existing = find_toolkit_by_name(ctx, toolkit_name)
    if existing:
        existing_type = existing.get("type")
        if existing_type != toolkit_type:
            error_msg = f"Toolkit name collision: '{toolkit_name}' exists with type '{existing_type}', but requested type is '{toolkit_type}'"
            ctx.log(f"ERROR: {error_msg}", "error")
            return {"success": False, "error": error_msg}
        
        ctx.log(f"Toolkit already exists with ID: {existing['id']} (type: {existing_type})", "info")
        return {"success": True, "id": existing["id"], "name": toolkit_name, "existed": True}

    # Create toolkit via API
    url = f"{ctx.base_url}/api/v2/elitea_core/tools/prompt_lib/{ctx.project_id}"
    response = requests.post(url, headers=ctx.get_headers(True), json=toolkit_config)

    if response.status_code in (200, 201):
        data = response.json()
        toolkit_id = data.get("id")
        ctx.log(f"Created toolkit with ID: {toolkit_id}", "success")
        ctx.created_resources.append({"type": "toolkit", "id": toolkit_id, "name": toolkit_name})
        return {"success": True, "id": toolkit_id, "name": toolkit_name}
    else:
        error = response.text[:200]
        ctx.log(f"Failed to create toolkit: {response.status_code} - {error}", "error")
        return {"success": False, "error": error}


def find_toolkit_by_name(ctx: SetupContext, name: str) -> Optional[dict]:
    """Find a toolkit by name."""
    url = f"{ctx.base_url}/api/v2/elitea_core/tools/prompt_lib/{ctx.project_id}?limit=500"
    response = requests.get(url, headers=ctx.get_headers())

    if response.status_code == 200:
        for toolkit in response.json().get("rows", []):
            if toolkit.get("name") == name:
                return toolkit
    return None


# =============================================================================
# Configuration Management
# =============================================================================


def get_configurations(ctx: SetupContext, type_filter: str = None) -> list[dict]:
    """Get list of configurations for the project."""
    url = f"{ctx.base_url}/api/v2/configurations/configurations/{ctx.project_id}?limit=100"
    if type_filter:
        url += f"&type={type_filter}"
    response = requests.get(url, headers=ctx.get_headers())

    if response.status_code == 200:
        return response.json().get("items", [])
    return []


def find_configuration_by_title(ctx: SetupContext, alita_title: str, type_filter: str = None) -> Optional[dict]:
    """Find a configuration by its alita_title."""
    configs = get_configurations(ctx, type_filter)
    for config in configs:
        if config.get("alita_title") == alita_title:
            return config
    return None


def create_configuration(ctx: SetupContext, config_type: str, label: str, alita_title: str, data: dict) -> dict:
    """Create a configuration in the project."""
    url = f"{ctx.base_url}/api/v2/configurations/configurations/{ctx.project_id}"
    payload = {
        "type": config_type,
        "label": label,
        "alita_title": alita_title,
        "section": "credentials",
        "data": data,
    }
    response = requests.post(url, headers=ctx.get_headers(True), json=payload)

    if response.status_code in (200, 201):
        ctx.log(f"Created configuration: {label}", "success")
        return {"success": True, "config": response.json()}
    else:
        ctx.log(f"Failed to create configuration: {response.text[:200]}", "error")
        return {"success": False, "error": response.text[:200]}


def update_configuration(ctx: SetupContext, config_id: int, data: dict) -> dict:
    """Update an existing configuration."""
    url = f"{ctx.base_url}/api/v2/configurations/configuration/{ctx.project_id}/{config_id}"
    response = requests.put(url, headers=ctx.get_headers(True), json={"data": data})

    if response.status_code in (200, 201):
        ctx.log(f"Updated configuration ID: {config_id}", "success")
        return {"success": True}
    else:
        ctx.log(f"Failed to update configuration: {response.text[:200]}", "error")
        return {"success": False, "error": response.text[:200]}


def _is_valid_config_value(value: Any) -> bool:
    """Check if a configuration value is valid (not empty, not unresolved variable)."""
    if value is None:
        return False
    if isinstance(value, str):
        # Empty or whitespace-only
        if not value.strip():
            return False
        # Unresolved environment variable (e.g., ${VAR_NAME})
        if value.startswith("${") and value.endswith("}"):
            return False
        # Partial unresolved (e.g., contains ${)
        if "${" in value:
            return False
    return True


def ensure_configuration(ctx: SetupContext, config_type: str, alita_title: str, data: dict) -> dict:
    """
    Ensure a configuration exists with the specified data.

    This is generic and works with any configuration type (github, jira, etc.).
    The data dict should contain all the fields needed for that configuration type.

    Smart update behavior:
    - If configuration doesn't exist, creates it (requires all data to be valid)
    - If configuration exists, only updates with fields that have valid (resolved) values
    - If existing config has secrets but new data has unresolved vars, preserves existing
    """
    existing = find_configuration_by_title(ctx, alita_title, config_type)

    if ctx.dry_run:
        if existing:
            ctx.log(f"[DRY RUN] Would update configuration: {alita_title}", "info")
        else:
            ctx.log(f"[DRY RUN] Would create configuration: {alita_title}", "info")
        return {"success": True, "dry_run": True}

    if existing:
        # Smart update: only include fields with valid (resolved) values
        # This prevents overwriting existing secrets with unresolved ${VAR} placeholders
        update_data = {}
        skipped_fields = []

        for key, value in data.items():
            if _is_valid_config_value(value):
                update_data[key] = value
            else:
                skipped_fields.append(key)

        if skipped_fields:
            ctx.log(f"Skipping unresolved fields: {', '.join(skipped_fields)}", "info")

        if not update_data:
            ctx.log(f"Configuration '{alita_title}' exists, no valid updates to apply", "info")
            return {"success": True, "skipped": True, "reason": "no valid update data"}

        ctx.log(f"Configuration '{alita_title}' exists (ID: {existing['id']}), updating fields: {list(update_data.keys())}", "info")
        return update_configuration(ctx, existing["id"], update_data)
    else:
        # For new configurations, check if we have the minimum required data
        invalid_fields = [k for k, v in data.items() if not _is_valid_config_value(v)]
        if invalid_fields:
            ctx.log(f"Cannot create configuration - unresolved fields: {', '.join(invalid_fields)}", "warning")
            return {"success": False, "error": f"Unresolved environment variables: {', '.join(invalid_fields)}"}

        ctx.log(f"Creating configuration '{alita_title}'...", "info")
        return create_configuration(ctx, config_type, alita_title.title(), alita_title, data)


def handle_configuration(step: dict, ctx: SetupContext) -> dict:
    """
    Handle configuration creation/update for setup.

    This is toolkit-agnostic - it creates any type of configuration
    based on the config.yaml specification.

    Config should contain:
      - config_type: The configuration type (github, jira, confluence, etc.)
      - alita_title: The configuration title/name
      - data: The configuration data (fields depend on config_type)
    """
    config = resolve_env_value(step.get("config", {}), ctx.env_vars, env_loader=load_from_env)

    config_type = config.get("config_type")
    alita_title = config.get("alita_title")
    data = config.get("data", {})

    if not config_type:
        ctx.log("No config_type provided", "warning")
        return {"success": True, "skipped": True, "reason": "no config_type"}

    if not alita_title:
        ctx.log("No alita_title provided", "warning")
        return {"success": True, "skipped": True, "reason": "no alita_title"}

    ctx.log(f"Ensuring configuration '{alita_title}' of type '{config_type}'")

    return ensure_configuration(ctx, config_type, alita_title, data)


# =============================================================================
# User Token Management
# =============================================================================


def get_user_tokens(ctx: SetupContext) -> list[dict]:
    """Get list of API tokens for the current user."""
    url = f"{ctx.base_url}/api/v2/auth/token"
    response = requests.get(url, headers=ctx.get_headers())

    if response.status_code == 200:
        return response.json()
    return []


def create_user_token(ctx: SetupContext, name: str, expires_days: int = None) -> dict:
    """Create an API token for the current user."""
    url = f"{ctx.base_url}/api/v2/auth/token"
    payload = {"name": name}
    if expires_days:
        payload["expires"] = {"measure": "days", "value": expires_days}

    response = requests.post(url, headers=ctx.get_headers(True), json=payload)

    if response.status_code in (200, 201):
        token_data = response.json()
        ctx.log(f"Created user API token: {name}", "success")
        return {"success": True, "token": token_data}
    else:
        ctx.log(f"Failed to create user token: {response.text[:200]}", "error")
        return {"success": False, "error": response.text[:200]}


def ensure_user_token(ctx: SetupContext, token_name: str = "api") -> dict:
    """Ensure the current user has an API token for synchronous tool invocation."""
    if ctx.dry_run:
        ctx.log(f"[DRY RUN] Would ensure user API token '{token_name}' exists", "info")
        return {"success": True, "dry_run": True}

    tokens = get_user_tokens(ctx)
    for token in tokens:
        if token.get("name") == token_name:
            ctx.log(f"User API token '{token_name}' exists", "info")
            return {"success": True, "existed": True}

    # Create token if not exists
    return create_user_token(ctx, token_name)


def handle_toolkit_invoke(step: dict, ctx: SetupContext) -> dict:
    """
    Handle generic toolkit tool invocation for setup.

    This is toolkit-agnostic - it simply invokes the specified tool with
    the specified parameters. The config should contain:
      - toolkit_id: The toolkit ID to invoke
      - tool_name: The tool to call
      - tool_params: Parameters to pass to the tool (optional)
    """
    config = resolve_env_value(step.get("config", {}), ctx.env_vars, env_loader=load_from_env)

    toolkit_id = config.get("toolkit_id") or config.get("toolkit_ref")
    tool_name = config.get("tool_name")
    tool_params = config.get("tool_params", {})

    if not toolkit_id:
        ctx.log("No toolkit_id provided", "warning")
        return {"success": True, "skipped": True, "reason": "no toolkit_id"}

    if not tool_name:
        ctx.log("No tool_name provided", "warning")
        return {"success": True, "skipped": True, "reason": "no tool_name"}

    ctx.log(f"Invoking toolkit {toolkit_id} tool: {tool_name}")

    if ctx.dry_run:
        ctx.log(f"[DRY RUN] Would invoke {tool_name} with params: {tool_params}")
        return {"success": True, "dry_run": True}

    result = invoke_toolkit_tool(ctx, int(toolkit_id), tool_name, tool_params)

    if result.get("success"):
        ctx.log(f"Tool {tool_name} executed successfully", "success")
    else:
        ctx.log(f"Tool {tool_name} failed: {result.get('error', 'Unknown error')}", "error")

    return result


def get_toolkit_by_id(ctx: SetupContext, toolkit_id: int) -> Optional[dict]:
    """Get toolkit details by ID."""
    url = f"{ctx.base_url}/api/v2/elitea_core/tool/prompt_lib/{ctx.project_id}/{toolkit_id}"
    response = requests.get(url, headers=ctx.get_headers())
    if response.status_code == 200:
        return response.json()
    return None


def invoke_toolkit_tool(ctx: SetupContext, toolkit_id: int, tool_name: str, params: dict) -> dict:
    """Invoke a tool from a toolkit using the test_toolkit_tool API."""
    # First, get the full toolkit configuration
    toolkit = get_toolkit_by_id(ctx, toolkit_id)
    if not toolkit:
        return {"success": False, "error": f"Toolkit {toolkit_id} not found"}

    # Build toolkit_config for test_toolkit_tool API
    toolkit_config = {
        "type": toolkit.get("type", "github"),
        "toolkit_name": toolkit.get("name"),
        "settings": toolkit.get("settings", {}),
    }

    url = f"{ctx.base_url}/api/v2/elitea_core/test_toolkit_tool/prompt_lib/{ctx.project_id}?await_response=true"

    payload = {
        "toolkit_config": toolkit_config,
        "tool_name": tool_name,
        "tool_params": params,
    }

    ctx.log(f"Invoking tool {tool_name} via test_toolkit_tool API...")

    response = requests.post(url, headers=ctx.get_headers(True), json=payload, timeout=120)

    if response.status_code == 200:
        result = response.json()
        # Extract the actual tool result from the response
        if result.get("result"):
            tool_result = result.get("result")
            return {"success": True, "result": tool_result}
        return {"success": True, "result": result}
    else:
        return {"success": False, "error": response.text}


# =============================================================================
# Main Setup Execution
# =============================================================================

# Import strategy classes
from setup_strategy import (
    SetupStrategy,
    RemoteSetupStrategy,
    LocalSetupStrategy,
    get_default_strategy,
)


def execute_setup(
    config: dict,
    ctx: SetupContext,
    base_path: Path,
    strategy: SetupStrategy = None
) -> dict:
    """Execute all setup steps from config.
    
    Args:
        config: Suite configuration dict containing 'setup' steps
        ctx: SetupContext with environment and authentication
        base_path: Base path for resolving relative file paths
        strategy: SetupStrategy to use for step execution.
                 Defaults to RemoteSetupStrategy if not provided.
    
    Returns:
        Dict with 'success', 'steps', and 'env_vars' keys
    """
    # Use default strategy (Remote) if none provided
    if strategy is None:
        strategy = get_default_strategy()
    
    setup_steps = config.get("setup", [])
    results = {"success": True, "steps": [], "env_vars": {}}

    if ctx.logger:
        ctx.logger.section(f"Executing setup for: {config.get('name', 'unknown')}")
        ctx.logger.info(f"Steps: {len(setup_steps)}")
    elif ctx.verbose or ctx.dry_run:
        print(f"\nExecuting setup for: {config.get('name', 'unknown')}")
        print(f"Steps: {len(setup_steps)}")
        print("-" * 60)

    for i, step in enumerate(setup_steps, 1):
        step_name = step.get("name", f"Step {i}")
        step_type = step.get("type")
        action = step.get("action", "")

        # Log step progress - use logger if available, else fallback to print
        if ctx.logger:
            ctx.logger.info(f"[{i}/{len(setup_steps)}] {step_name}")
        elif ctx.verbose:
            print(f"\n[{i}/{len(setup_steps)}] {step_name}")

        # Check if step is enabled
        if not step.get("enabled", True):
            ctx.log("Step disabled, skipping", "info")
            results["steps"].append({"name": step_name, "skipped": True})
            continue

        # Execute step based on type using strategy
        step_result = {"success": False, "error": "Unknown step type"}

        try:
            if step_type == "toolkit":
                # Create or update toolkit entity
                if action == "create_or_update":
                    step_result = strategy.handle_toolkit_create(step, ctx, base_path)
                else:
                    step_result = {"success": False, "error": f"Unknown toolkit action: {action}"}
            elif step_type == "toolkit_invoke":
                # Generic toolkit tool invocation
                step_result = strategy.handle_toolkit_invoke(step, ctx)
            elif step_type == "configuration":
                # Create or ensure configurations exist
                step_result = strategy.handle_configuration(step, ctx)
            else:
                step_result = {"success": False, "error": f"Unknown step type: {step_type}"}
        except Exception as e:
            step_result = {"success": False, "error": str(e)}

        # Save environment variables from step result
        if step_result.get("success") and "save_to_env" in step:
            for save_config in step["save_to_env"]:
                import json
                key = save_config["key"]
                value_path = save_config["value"]
                default_value = save_config.get("default")
                
                # Debug: Show what we're working with
                ctx.log(f"[DEBUG] save_to_env for key '{key}':", "info")
                ctx.log(f"  Path: {value_path}", "info")
                ctx.log(f"  Default: {default_value}", "info")
                ctx.log(f"  step_result keys: {list(step_result.keys())}", "info")
                ctx.log(f"  step_result type: {type(step_result)}", "info")
                
                # Show relevant portion of step_result
                if "result" in step_result:
                    result_preview = json.dumps(step_result["result"], indent=2)[:500]
                    ctx.log(f"  step_result['result']: {result_preview}...", "info")
                else:
                    ctx.log(f"  step_result (no 'result' key): {json.dumps(step_result, indent=2)[:500]}...", "info")
                
                # Extract value using JSONPath
                value = extract_json_path(step_result, value_path)
                ctx.log(f"  Extracted value: {value} (type: {type(value).__name__})", "info")
                
                # If JSONPath failed and result is a string, try regex extraction
                if value is None and "result" in step_result:
                    result_data = step_result["result"]
                    # Check if result is nested dict with 'result' field (toolkit response format)
                    if isinstance(result_data, dict) and "result" in result_data:
                        result_data = result_data["result"]
                    
                    if isinstance(result_data, str):
                        # Try to extract issue keys from formatted string output
                        # Pattern matches: 'key': 'EL-455' or "key": "EL-455"
                        # Determine which match index to use based on JSONPath
                        match_index = 0
                        if "[1]" in value_path:
                            match_index = 1
                        elif "[2]" in value_path:
                            match_index = 2
                        
                        # Try single-quoted format first
                        value = extract_regex_match(result_data, r"'key': '([A-Z]+-\d+)'", match_index=match_index)
                        if value is None:
                            # Try double-quoted format
                            value = extract_regex_match(result_data, r'"key": "([A-Z]+-\d+)"', match_index=match_index)
                        
                        if value is not None:
                            ctx.log(f"  Extracted via regex (match #{match_index}): {value}", "info")
                
                # Use default if extraction failed
                if value is None and default_value is not None:
                    # Resolve any environment variable references in the default value
                    value = resolve_env_value(default_value, ctx.env_vars, env_loader=load_from_env)
                    ctx.log(f"  Using default value: {value}", "info")
                
                if value is not None:
                    # In dry_run mode, don't overwrite existing env values with dummy data
                    if step_result.get("dry_run") and key in ctx.env_vars:
                        ctx.log(f"Keeping existing {key}={ctx.env_vars[key]}", "info")
                    else:
                        ctx.log(f"Saved {key}={value}", "info")
                        ctx.save_env(key, value)
                else:
                    ctx.log(f"[WARNING] Not saving {key} - value is None and no default provided", "warning")

        results["steps"].append({
            "name": step_name,
            "type": step_type,
            "action": action,
            **step_result,
        })

        # Handle failure
        if not step_result.get("success") and not step_result.get("dry_run"):
            if not step.get("continue_on_error", False):
                ctx.log(f"Setup failed at step: {step_name}", "error")
                results["success"] = False
                break

    # Copy final env vars to results
    results["env_vars"] = dict(ctx.env_vars)

    return results


def write_env_file(env_vars: dict, output_path: Path):
    """Write environment variables to a file."""
    with open(output_path, "w") as f:
        f.write("# Generated by setup.py\n")
        f.write(f"# Timestamp: {datetime.now().isoformat()}\n\n")
        for key, value in env_vars.items():
            f.write(f"{key}={value}\n")


def run(
    folder: str,
    env_file: str | Path | None = None,
    output_env: str | Path | None = None,
    base_url: str | None = None,
    project_id: int | None = None,
    token: str | None = None,
    dry_run: bool = False,
    verbose: bool = False,
    quiet: bool = False,
    local: bool = False,
    logger: TestLogger = None,
) -> dict:
    """Run set up programmatically.
    
    Args:
        folder: Suite folder name
        env_file: Path to env file to load
        output_env: Path to write generated env vars
        base_url: Platform base URL
        project_id: Project ID
        token: Bearer token for authentication
        dry_run: Show what would be done without executing
        verbose: Enable verbose output
        quiet: Suppress non-error output
        local: Local mode - prepare environment without backend calls
        logger: TestLogger instance for unified logging
    """
    # Create logger if not provided
    if logger is None:
        logger = TestLogger(verbose=verbose, quiet=quiet)
    
    # In local mode, we prepare environment using local toolkits
    if local:
        logger.info("[LOCAL MODE] Using local toolkit creation (no backend)")
    
    # Load environment file if provided
    if env_file:
        env_file_path = Path(env_file)
        if not env_file_path.exists():
            raise FileNotFoundError(f"Env file not found: {env_file}")
        set_env_file(env_file_path)

    # Parse suite specification and resolve paths
    folder_name, pipeline_file = parse_suite_spec(folder)
    script_dir = Path(__file__).parent
    base_dir = script_dir.parent  # Go up from scripts/ to test_pipelines/
    suite_folder = base_dir / folder_name

    if not suite_folder.exists():
        raise FileNotFoundError(f"Suite folder not found: {suite_folder}")

    # Load configuration
    config = load_config(suite_folder, pipeline_file)
    if not config:
        raise FileNotFoundError(f"Config not found in {suite_folder}")

    # Resolve settings
    base_url = base_url or load_base_url_from_env() or DEFAULT_BASE_URL
    project_id = project_id or load_project_id_from_env() or DEFAULT_PROJECT_ID
    bearer_token = token or load_token_from_env()

    if not bearer_token and not dry_run:
        raise ValueError("Authentication token required.")

    # Create context
    ctx = SetupContext(
        base_url=base_url,
        project_id=project_id,
        bearer_token=bearer_token or "",
        verbose=verbose,
        dry_run=dry_run,
        logger=logger,
    )
    
    # Load env_mapping values before setup
    if config:
        for key, value in config.get("env_mapping", {}).items():
            resolved_value = resolve_env_value(value, ctx.env_vars, env_loader=load_from_env)
            ctx.env_vars[key] = resolved_value
            if verbose or dry_run:
                logger.debug(f"Loaded env_mapping: {key}={resolved_value}")
    
    logger.section(f"Setup: {config.get('name', folder)}")
    logger.info(f"Target: {base_url} (Project: {project_id})")
    if dry_run:
        logger.info("[DRY RUN MODE]")

    # Execute setup
    results = execute_setup(config, ctx, suite_folder)

    # Write env file if requested
    if output_env and results["env_vars"]:
        env_path = Path(output_env)
        write_env_file(results["env_vars"], env_path)
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Execute setup steps from a test suite's config.yaml",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument("folder", help="Suite folder name (e.g., 'github_toolkit' or 'github_toolkit_negative:pipeline_validation.yaml')")
    parser.add_argument("--base-url", default=None, help="Platform base URL")
    parser.add_argument("--project-id", type=int, default=None, help="Project ID")
    parser.add_argument("--token", help="Bearer token for authentication")
    parser.add_argument(
        "--env-file",
        help="Load environment variables from a specific file (e.g., existing .env)",
    )
    parser.add_argument("--local", action="store_true", 
                        help="Local mode: prepare environment without backend calls")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without executing")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--output-env", "-o", help="Write generated env vars to file")
    parser.add_argument("--json", "-j", action="store_true", help="Output results as JSON")

    args = parser.parse_args()

    # Create logger
    logger = TestLogger(verbose=args.verbose, quiet=args.json)
    
    try:
        results = run(
            folder=args.folder,
            env_file=args.env_file,
            output_env=args.output_env,
            base_url=args.base_url,
            project_id=args.project_id,
            token=args.token,
            dry_run=args.dry_run,
            verbose=args.verbose,
            quiet=args.json,
            local=args.local,
            logger=logger,
        )
    except Exception as e:
        if args.json:
            print(json.dumps({"success": False, "error": str(e)}))
        else:
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Output results
    if args.json:
        print(json.dumps(results, indent=2, default=str))
    else:
        logger.section("Setup Results")
        for step in results["steps"]:
            status = "✓" if step.get("success") else ("⊘" if step.get("skipped") else "✗")
            logger.info(f"{status} {step['name']}")
            if step.get("error"):
                logger.error(f"  Error: {step['error'][:100]}")

        logger.info("\nEnvironment Variables:")
        for key, value in results["env_vars"].items():
            # Mask sensitive values
            display_value = value if "TOKEN" not in key.upper() else f"{str(value)[:4]}***"
            logger.info(f"{key}={display_value}")
        
        if args.output_env:
             logger.success(f"Environment written to: {args.output_env}")

    # Exit with appropriate code
    if not results["success"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
