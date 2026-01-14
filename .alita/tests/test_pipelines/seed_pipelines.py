#!/usr/bin/env python3
"""
Seed test pipelines to Elitea platform via REST API.

This script seeds both test pipelines and composable pipelines (if defined in config.yaml).
Composable pipelines are seeded first so their IDs can be used by test pipelines and hooks.

Usage:
    python seed_pipelines.py <folder_name> [--base-url URL] [--project-id ID] [--token TOKEN]

Example:
    python seed_pipelines.py state_retrieval --project-id 2
    python seed_pipelines.py github_toolkit --base-url http://192.168.68.115 --project-id 2
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import requests
import yaml


DEFAULT_BASE_URL = "http://192.168.68.115"
DEFAULT_PROJECT_ID = 2
DEFAULT_LLM_SETTINGS = {
    "model_name": "gpt-5-mini",
    "temperature": 0.5,
    "max_tokens": 4096,
}

# Global env file override (set via --env-file CLI option)
_env_file_override: Path | None = None


def set_env_file(env_file: str | Path | None):
    """Set a custom env file to load variables from (has highest priority)."""
    global _env_file_override
    if env_file:
        _env_file_override = Path(env_file)
    else:
        _env_file_override = None


def load_from_env(var_name: str) -> str | None:
    """Load value from environment variable or .env file.

    Priority order:
    1. Custom env file (if set via --env-file)
    2. OS environment variables
    3. Default .env file locations
    """
    # First check custom env file if set
    if _env_file_override and _env_file_override.exists():
        with open(_env_file_override) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and line.startswith(f"{var_name}="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")

    # Then check OS environment
    value = os.environ.get(var_name)
    if value:
        return value

    # Finally try default .env file locations
    env_paths = [
        Path(__file__).parent / ".env",
        Path(__file__).parent.parent.parent.parent / ".env",  # alita-sdk root
        Path(__file__).parent.parent.parent.parent.parent / ".env",  # elitea root
    ]

    for env_path in env_paths:
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and line.startswith(f"{var_name}="):
                        return line.split("=", 1)[1].strip().strip('"').strip("'")

    return None


def load_session_from_env():
    """Load session cookie from environment variable or .env file."""
    return load_from_env("ELITEA_SESSION")


def load_token_from_env():
    """Load API token from environment variable or .env file."""
    return load_from_env("AUTH_TOKEN") or load_from_env("ELITEA_TOKEN") or load_from_env("API_KEY")


def load_base_url_from_env():
    """Load base URL from environment variable or .env file."""
    return load_from_env("BASE_URL") or load_from_env("DEPLOYMENT_URL")


def load_project_id_from_env():
    """Load project ID from environment variable or .env file."""
    value = load_from_env("PROJECT_ID")
    if value:
        try:
            return int(value)
        except ValueError:
            pass
    return None


def load_github_toolkit_id_from_env():
    """Load GitHub toolkit ID from environment variable or .env file."""
    value = load_from_env("GITHUB_TOOLKIT_ID")
    if value:
        try:
            return int(value)
        except ValueError:
            pass
    return None


def load_github_toolkit_name_from_env():
    """Load GitHub toolkit name from environment variable or .env file."""
    return load_from_env("GITHUB_TOOLKIT_NAME")


def load_sdk_toolkit_id_from_env():
    """Load SDK toolkit ID from environment variable or .env file."""
    value = load_from_env("SDK_TOOLKIT_ID")
    if value:
        try:
            return int(value)
        except ValueError:
            pass
    return None


def load_sdk_toolkit_name_from_env():
    """Load SDK toolkit name from environment variable or .env file."""
    return load_from_env("SDK_TOOLKIT_NAME")


def load_config(suite_folder: Path) -> dict | None:
    """Load pipeline.yaml (or config.yaml for backwards compatibility) from a suite folder if it exists."""
    # Try pipeline.yaml first (new convention)
    config_path = suite_folder / "pipeline.yaml"
    if not config_path.exists():
        # Fall back to config.yaml for backwards compatibility
        config_path = suite_folder / "config.yaml"
        if not config_path.exists():
            return None

    with open(config_path) as f:
        return yaml.safe_load(f)


def resolve_env_value(value: Any, env_substitutions: dict) -> Any:
    """Resolve environment variable references in a value.

    Handles patterns like ${VAR_NAME} and ${VAR_NAME:default}.
    """
    if isinstance(value, str):
        pattern = r'\$\{([^}:]+)(?::([^}]*))?\}'

        def replacer(match):
            var_name = match.group(1)
            default = match.group(2)

            # Check substitutions dict first
            if var_name in env_substitutions:
                return str(env_substitutions[var_name])
            # Then check environment
            env_value = load_from_env(var_name)
            if env_value:
                return env_value
            # Fall back to default
            if default is not None:
                return default
            return match.group(0)

        return re.sub(pattern, replacer, value)
    elif isinstance(value, dict):
        return {k: resolve_env_value(v, env_substitutions) for k, v in value.items()}
    elif isinstance(value, list):
        return [resolve_env_value(v, env_substitutions) for v in value]
    return value


def extract_json_path_value(data: dict, json_path: str) -> Any:
    """Extract a value from a dict using a simple JSON path like $.id or $.name."""
    if not json_path.startswith("$."):
        return None

    path = json_path[2:]  # Remove "$."
    parts = path.split(".")

    current = data
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def seed_composable_pipelines(
    config: dict,
    suite_folder: Path,
    base_url: str,
    project_id: int,
    llm_settings: dict,
    env_substitutions: dict,
    session_cookie: str = None,
    bearer_token: str = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict:
    """Seed composable pipelines defined in config.yaml.

    Composable pipelines are seeded first so their IDs can be used by:
    - Test pipelines (as toolkit participants)
    - Post-test hooks (for RCA, notifications, etc.)

    Args:
        config: Loaded config.yaml dict
        suite_folder: Path to the suite folder
        base_url: Platform base URL
        project_id: Project ID
        llm_settings: LLM settings for pipelines
        env_substitutions: Dict of env vars to substitute (will be updated with new IDs)
        session_cookie: Session cookie for auth
        bearer_token: Bearer token for auth
        dry_run: If True, don't actually create pipelines
        verbose: If True, print detailed output

    Returns:
        dict with seeded pipeline info and updated env_substitutions
    """
    composable_pipelines = config.get("composable_pipelines", [])
    if not composable_pipelines:
        return {"success": True, "pipelines": [], "env_substitutions": env_substitutions, "generated_env_vars": {}}

    print(f"\nSeeding {len(composable_pipelines)} composable pipeline(s)...")
    print("-" * 40)

    results = {
        "success": True,
        "pipelines": [],
        "env_substitutions": env_substitutions.copy(),
        "generated_env_vars": {}  # Track vars generated during seeding (for .env persistence)
    }
    script_dir = Path(__file__).parent

    for cp_config in composable_pipelines:
        file_path = cp_config.get("file")
        if not file_path:
            print("  Warning: Composable pipeline missing 'file' key, skipping")
            continue

        # Resolve relative path from suite folder
        if file_path.startswith("../"):
            yaml_path = (suite_folder / file_path).resolve()
        else:
            yaml_path = suite_folder / file_path

        if not yaml_path.exists():
            # Also try from script directory
            yaml_path = (script_dir / file_path.lstrip("./")).resolve()

        if not yaml_path.exists():
            print(f"  Warning: Composable pipeline file not found: {file_path}")
            continue

        # Build substitutions for this composable pipeline
        cp_env = results["env_substitutions"].copy()
        for key, value in cp_config.get("env", {}).items():
            cp_env[key] = resolve_env_value(value, cp_env)

        # Parse and seed the pipeline
        pipeline_data = parse_pipeline_yaml(yaml_path, env_substitutions=cp_env)
        print(f"\n[composable] {pipeline_data['name']}")

        if dry_run:
            payload = create_application_payload(pipeline_data, llm_settings)
            if verbose:
                print(f"  Payload: {json.dumps(payload, indent=2)}")
            else:
                print(f"  Would create: {payload['name']}")
            results["pipelines"].append({
                "file": file_path,
                "name": pipeline_data["name"],
                "dry_run": True,
            })
            continue

        result = seed_pipeline(
            base_url,
            project_id,
            pipeline_data,
            llm_settings,
            session_cookie=session_cookie,
            bearer_token=bearer_token,
        )

        if result["success"]:
            app_id = result["data"].get("id")
            version_id = result["data"].get("versions", [{}])[0].get("id")

            print(f"  Created successfully (ID: {app_id})")

            # Link toolkits if any are defined
            toolkit_ids = pipeline_data.get("toolkit_ids", [])
            if toolkit_ids and version_id:
                for toolkit_id in toolkit_ids:
                    link_result = link_toolkit_to_application(
                        base_url=base_url,
                        project_id=project_id,
                        toolkit_id=toolkit_id,
                        application_id=app_id,
                        version_id=version_id,
                        session_cookie=session_cookie,
                        bearer_token=bearer_token,
                    )
                    if link_result.get("success"):
                        print(f"    Linked toolkit {toolkit_id}")
                    else:
                        print(f"    Failed to link toolkit {toolkit_id}: {link_result.get('error', 'Unknown error')}")

            # Save to env_substitutions if save_to_env is defined
            for save_item in cp_config.get("save_to_env", []):
                key = save_item.get("key")
                json_path = save_item.get("value")
                if key and json_path:
                    extracted = extract_json_path_value(result["data"], json_path)
                    if extracted is not None:
                        results["env_substitutions"][key] = extracted
                        results["generated_env_vars"][key] = extracted  # Track as generated
                        print(f"    Saved {key}={extracted}")

            results["pipelines"].append({
                "file": file_path,
                "name": pipeline_data["name"],
                "id": app_id,
                "version_id": version_id,
            })
        else:
            print(f"  FAILED: {result.get('status_code', 'N/A')} - {result.get('error', 'Unknown error')}")
            results["success"] = False
            results["pipelines"].append({
                "file": file_path,
                "name": pipeline_data["name"],
                "error": result.get("error"),
            })

    return results


def get_yaml_files(folder_path: Path, config: dict = None) -> list[Path]:
    """Get all YAML test case files from the specified folder.

    Args:
        folder_path: Base suite folder path
        config: Optional config dict that may specify test_directory

    Returns:
        List of test case YAML files sorted by name
    """
    # Check if config specifies a test_directory
    test_dir = folder_path
    if config and "execution" in config:
        test_subdir = config["execution"].get("test_directory")
        if test_subdir:
            test_dir = folder_path / test_subdir

    yaml_files = []
    for pattern in ["test_case_*.yaml", "test_case_*.yml"]:
        yaml_files.extend(test_dir.glob(pattern))
    return sorted(yaml_files)


def parse_pipeline_yaml(yaml_path: Path, env_substitutions: dict = None) -> dict:
    """Parse a pipeline YAML file and extract metadata.

    The YAML file format is:
        name: "Pipeline Name"
        description: "Description"
        toolkits:  # optional - toolkit participants
          - id: 1
            name: github
        state:
          ...
        entry_point: ...
        nodes:
          ...

    The name and description are extracted for the application metadata,
    and the remaining YAML (toolkits, state, entry_point, nodes) becomes the instructions.
    Preserves original YAML formatting to avoid issues with yaml.dump.

    Args:
        yaml_path: Path to the YAML file
        env_substitutions: Dict of environment variable substitutions to apply
                          e.g., {"GITHUB_TOOLKIT_ID": 5} will replace ${GITHUB_TOOLKIT_ID} with 5
    """
    with open(yaml_path) as f:
        content = f.read()
        data = yaml.safe_load(content)

    name = data.get("name", yaml_path.stem)
    description = data.get("description", "")

    # Apply environment variable substitutions to name and description
    if env_substitutions:
        name = resolve_env_value(name, env_substitutions)
        description = resolve_env_value(description, env_substitutions)

    # Extract toolkit IDs for later linking (before substitution to get the raw values)
    toolkits = data.get("toolkits", [])
    toolkit_ids = []
    for tk in toolkits:
        tk_id = tk.get("id")
        if tk_id is not None:
            # Handle ${VAR} substitution patterns
            if isinstance(tk_id, str) and tk_id.startswith("${") and tk_id.endswith("}"):
                var_name = tk_id[2:-1]
                if env_substitutions and var_name in env_substitutions:
                    toolkit_ids.append(int(env_substitutions[var_name]))
            elif isinstance(tk_id, int):
                toolkit_ids.append(tk_id)

    # Find where pipeline config starts (toolkits, state, entry_point, or nodes)
    # This preserves exact YAML formatting (indentation, multiline strings, quotes)
    lines = content.split('\n')
    start_idx = None
    for i, line in enumerate(lines):
        # Find first line that starts a pipeline config key (not name/description)
        stripped = line.strip()
        if stripped and not stripped.startswith('#'):
            if any(stripped.startswith(f"{key}:") for key in ('toolkits', 'state', 'entry_point', 'nodes')):
                start_idx = i
                break

    if start_idx is not None:
        instructions_yaml = '\n'.join(lines[start_idx:])
    else:
        # Fallback to yaml.dump if we can't find the start
        instructions_data = {k: v for k, v in data.items() if k not in ("name", "description")}
        instructions_yaml = yaml.dump(instructions_data, default_flow_style=False, allow_unicode=True, sort_keys=False)

    # Apply environment variable substitutions
    if env_substitutions:
        for var_name, value in env_substitutions.items():
            # Replace ${VAR_NAME} patterns
            instructions_yaml = instructions_yaml.replace(f"${{{var_name}}}", str(value))
            # Also replace $VAR_NAME patterns (without braces)
            instructions_yaml = instructions_yaml.replace(f"${var_name}", str(value))

    return {
        "name": name,
        "description": description,
        "yaml_content": instructions_yaml,
        "toolkit_ids": toolkit_ids,
    }


def create_application_payload(pipeline_data: dict, llm_settings: dict = None) -> dict:
    """Create the API payload for creating an application."""
    settings = llm_settings or DEFAULT_LLM_SETTINGS.copy()

    return {
        "name": pipeline_data["name"],
        "description": pipeline_data["description"],
        "versions": [
            {
                "name": "latest",
                "llm_settings": settings,
                "instructions": pipeline_data["yaml_content"],
                "agent_type": "pipeline",
                "tags": [],
                "tools": [],
                "variables": [],
                "meta": {
                    "step_limit": 25,
                },
            }
        ],
    }


def link_toolkit_to_application(
    base_url: str,
    project_id: int,
    toolkit_id: int,
    application_id: int,
    version_id: int,
    session_cookie: str = None,
    bearer_token: str = None,
) -> dict:
    """Link a toolkit to an application version via the relation API.

    Args:
        base_url: Platform base URL
        project_id: Project ID
        toolkit_id: ID of the toolkit to link
        application_id: ID of the application (pipeline)
        version_id: ID of the application version
        session_cookie: Session cookie for auth
        bearer_token: Bearer token for auth

    Returns:
        dict with success status and response data
    """
    url = f"{base_url}/api/v2/elitea_core/tool/prompt_lib/{project_id}/{toolkit_id}"

    payload = {
        "entity_id": application_id,
        "entity_version_id": version_id,
        "entity_type": "agent",
        "has_relation": True,
    }

    headers = {
        "Content-Type": "application/json",
    }

    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    elif session_cookie:
        headers["Cookie"] = f"centry_auth_session={session_cookie}"

    response = requests.patch(url, json=payload, headers=headers)

    if response.status_code == 201:
        return {"success": True, "data": response.json()}
    else:
        return {
            "success": False,
            "status_code": response.status_code,
            "error": response.text,
        }


def seed_pipeline(
    base_url: str,
    project_id: int,
    pipeline_data: dict,
    llm_settings: dict = None,
    session_cookie: str = None,
    bearer_token: str = None,
) -> dict:
    """Seed a single pipeline to the platform."""
    url = f"{base_url}/api/v2/elitea_core/applications/prompt_lib/{project_id}"

    payload = create_application_payload(pipeline_data, llm_settings)

    headers = {
        "Content-Type": "application/json",
    }

    # Use Bearer token if provided, otherwise use session cookie
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    elif session_cookie:
        headers["Cookie"] = f"centry_auth_session={session_cookie}"

    response = requests.post(url, json=payload, headers=headers)

    if response.status_code == 201:
        return {"success": True, "data": response.json()}
    else:
        return {
            "success": False,
            "status_code": response.status_code,
            "error": response.text,
        }


def main():
    parser = argparse.ArgumentParser(
        description="Seed test pipelines to Elitea platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s state_retrieval --token "your_api_key"
    %(prog)s structured_output --project-id 2 --token "your_api_key"
    %(prog)s state_retrieval --base-url http://localhost:8080 --session "your_session_cookie"

Environment Variables:
    AUTH_TOKEN, ELITEA_TOKEN, or API_KEY - Bearer token for authentication (preferred)
    ELITEA_SESSION - Session cookie value (centry_auth_session) for authentication
    BASE_URL or DEPLOYMENT_URL - Platform base URL
    GITHUB_TOOLKIT_ID - GitHub toolkit ID for substitution in pipeline YAML

Authentication (use one of these):
    --token: Bearer token (API key from Elitea settings)
    --session: Session cookie (from browser DevTools → Cookies → centry_auth_session)
        """,
    )

    parser.add_argument(
        "folder",
        help="Name of the folder within test_pipelines to seed (e.g., 'state_retrieval', 'structured_output')",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help=f"Base URL of the Elitea platform (default: from BASE_URL env or {DEFAULT_BASE_URL})",
    )
    parser.add_argument(
        "--project-id",
        type=int,
        default=None,
        help=f"Project ID to seed pipelines to (default: from PROJECT_ID env or {DEFAULT_PROJECT_ID})",
    )
    parser.add_argument(
        "--token",
        help="Bearer token (API key) for authentication (can also be set via ELITEA_TOKEN or API_KEY env var)",
    )
    parser.add_argument(
        "--session",
        help="Session cookie for authentication (can also be set via ELITEA_SESSION env var)",
    )
    parser.add_argument(
        "--model-name",
        default=DEFAULT_LLM_SETTINGS["model_name"],
        help=f"LLM model name (default: {DEFAULT_LLM_SETTINGS['model_name']})",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=DEFAULT_LLM_SETTINGS["temperature"],
        help=f"LLM temperature (default: {DEFAULT_LLM_SETTINGS['temperature']})",
    )
    parser.add_argument(
        "--github-toolkit-id",
        type=int,
        default=None,
        help="GitHub toolkit ID (can also be set via GITHUB_TOOLKIT_ID env var)",
    )
    parser.add_argument(
        "--env-file",
        help="Load environment variables from a specific file (e.g., .env.generated from setup.py)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print payloads without actually sending requests",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print detailed output",
    )

    args = parser.parse_args()

    # Set custom env file if provided (must be done before any load_from_env calls)
    if args.env_file:
        env_file_path = Path(args.env_file)
        if not env_file_path.exists():
            print(f"Error: Env file not found: {args.env_file}", file=sys.stderr)
            sys.exit(1)
        set_env_file(env_file_path)
        print(f"Loading environment from: {args.env_file}")

    # Resolve base URL and project ID from args or environment
    base_url = args.base_url or load_base_url_from_env() or DEFAULT_BASE_URL
    project_id = args.project_id or load_project_id_from_env() or DEFAULT_PROJECT_ID

    # Resolve folder path first (needed for SUITE_NAME)
    script_dir = Path(__file__).parent
    folder_path = script_dir / args.folder

    # Build environment substitutions for YAML templates
    # env_substitutions: used for YAML template variable substitution
    # generated_env_vars: track which vars were generated (vs loaded), for .env persistence
    env_substitutions = {}
    generated_env_vars = {}  # Only these will be written back to .env

    # GitHub toolkit
    github_toolkit_id = args.github_toolkit_id or load_github_toolkit_id_from_env()
    if github_toolkit_id is not None:  # Allow ID=0 (though unusual)
        env_substitutions["GITHUB_TOOLKIT_ID"] = github_toolkit_id
    github_toolkit_name = load_github_toolkit_name_from_env()
    if github_toolkit_name:
        env_substitutions["GITHUB_TOOLKIT_NAME"] = github_toolkit_name

    # SDK toolkit (for RCA and analysis)
    sdk_toolkit_id = load_sdk_toolkit_id_from_env()
    if sdk_toolkit_id is not None:
        env_substitutions["SDK_TOOLKIT_ID"] = sdk_toolkit_id
    sdk_toolkit_name = load_sdk_toolkit_name_from_env()
    if sdk_toolkit_name:
        env_substitutions["SDK_TOOLKIT_NAME"] = sdk_toolkit_name

    # Suite name (derived from folder name)
    suite_name = folder_path.name
    env_substitutions["SUITE_NAME"] = suite_name
    generated_env_vars["SUITE_NAME"] = suite_name  # This is generated, can persist

    if not folder_path.exists():
        print(f"Error: Folder '{folder_path}' does not exist", file=sys.stderr)
        sys.exit(1)

    if not folder_path.is_dir():
        print(f"Error: '{folder_path}' is not a directory", file=sys.stderr)
        sys.exit(1)

    # Get authentication credentials
    bearer_token = args.token or load_token_from_env()
    session_cookie = args.session or load_session_from_env()

    if not bearer_token and not session_cookie and not args.dry_run:
        print(
            "Error: Authentication required. Provide --token (API key) or --session (cookie)",
            file=sys.stderr,
        )
        print("  Set ELITEA_TOKEN/API_KEY or ELITEA_SESSION environment variable", file=sys.stderr)
        sys.exit(1)

    auth_method = "Bearer token" if bearer_token else "Session cookie"

    # Load pipeline.yaml if it exists (for composable pipelines and test_directory)
    config = load_config(folder_path)

    # Get YAML files (will look in test_directory if specified in config)
    yaml_files = get_yaml_files(folder_path, config)
    if not yaml_files and not (config and config.get("composable_pipelines")):
        print(f"No test case YAML files found in '{folder_path}'", file=sys.stderr)
        sys.exit(1)

    composable_count = len(config.get("composable_pipelines", [])) if config else 0
    print(f"Found {len(yaml_files)} test pipeline(s) in '{args.folder}'")
    if composable_count > 0:
        print(f"Found {composable_count} composable pipeline(s) in config.yaml")
    print(f"Target: {base_url} (Project ID: {project_id})")
    print(f"Auth: {auth_method}")
    if env_substitutions:
        print(f"Substitutions: {env_substitutions}")
    print("-" * 60)

    # Prepare LLM settings
    llm_settings = {
        "model_name": args.model_name,
        "temperature": args.temperature,
        "max_tokens": DEFAULT_LLM_SETTINGS["max_tokens"],
    }

    # Seed composable pipelines first (so their IDs can be used by test pipelines)
    if config and config.get("composable_pipelines"):
        composable_result = seed_composable_pipelines(
            config=config,
            suite_folder=folder_path,
            base_url=base_url,
            project_id=project_id,
            llm_settings=llm_settings,
            env_substitutions=env_substitutions,
            session_cookie=session_cookie,
            bearer_token=bearer_token,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )
        # Update env_substitutions with IDs from composable pipelines
        env_substitutions = composable_result["env_substitutions"]
        # Merge generated vars from composable pipelines
        generated_env_vars.update(composable_result.get("generated_env_vars", {}))

        if not composable_result["success"]:
            print("\nWarning: Some composable pipelines failed to seed")

    # Process each test pipeline
    results = {"success": 0, "failed": 0, "skipped": 0, "composable": composable_count}

    for yaml_file in yaml_files:
        pipeline_data = parse_pipeline_yaml(yaml_file, env_substitutions=env_substitutions)
        print(f"\n[{yaml_file.name}] {pipeline_data['name']}")

        if args.dry_run:
            payload = create_application_payload(pipeline_data, llm_settings)
            if args.verbose:
                print(f"  Payload: {json.dumps(payload, indent=2)}")
            else:
                print(f"  Would create: {payload['name']}")
            results["skipped"] += 1
            continue

        result = seed_pipeline(
            base_url,
            project_id,
            pipeline_data,
            llm_settings,
            session_cookie=session_cookie,
            bearer_token=bearer_token,
        )

        if result["success"]:
            app_id = result["data"].get("id", "unknown")
            # Get version ID from the response
            versions = result["data"].get("versions", [])
            version_id = versions[0].get("id") if versions else None

            print(f"  Created successfully (ID: {app_id})")

            # Link toolkits if any are defined
            toolkit_ids = pipeline_data.get("toolkit_ids", [])
            if toolkit_ids and version_id:
                for toolkit_id in toolkit_ids:
                    link_result = link_toolkit_to_application(
                        base_url=base_url,
                        project_id=project_id,
                        toolkit_id=toolkit_id,
                        application_id=app_id,
                        version_id=version_id,
                        session_cookie=session_cookie,
                        bearer_token=bearer_token,
                    )
                    if link_result["success"]:
                        print(f"    Linked toolkit {toolkit_id}")
                    else:
                        print(f"    Failed to link toolkit {toolkit_id}: {link_result.get('error', 'Unknown error')}")

            results["success"] += 1
        else:
            print(f"  FAILED: {result.get('status_code', 'N/A')} - {result.get('error', 'Unknown error')}")
            results["failed"] += 1

    # Write generated_env_vars back to .env file (for composable pipeline IDs, etc.)
    # Only persist values that were generated during seeding, not loaded from environment
    env_file = _env_file_override if _env_file_override else Path(".env")
    if env_file.exists() and generated_env_vars:
        # Read existing .env content
        with open(env_file, 'r') as f:
            lines = f.readlines()

        # Build dict of existing variables
        existing_vars = {}
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped and not stripped.startswith('#') and '=' in stripped:
                key = stripped.split('=', 1)[0]
                existing_vars[key] = i

        # Update or append new values from generated_env_vars
        updated = False
        for key, value in generated_env_vars.items():
            if key in existing_vars:
                # Update existing line
                lines[existing_vars[key]] = f"{key}={value}\n"
            else:
                # Append new variable
                lines.append(f"{key}={value}\n")
            updated = True

        # Write back if any updates were made
        if updated:
            with open(env_file, 'w') as f:
                f.writelines(lines)

    # Summary
    print("\n" + "=" * 60)
    summary_parts = [f"{results['success']} created", f"{results['failed']} failed"]
    if results["skipped"] > 0:
        summary_parts.append(f"{results['skipped']} skipped")
    if results.get("composable", 0) > 0:
        summary_parts.append(f"{results['composable']} composable")
    print(f"Summary: {', '.join(summary_parts)}")

    if results["failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
