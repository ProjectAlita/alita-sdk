#!/usr/bin/env python3
"""
Execute cleanup steps from a test suite's pipeline config.

This script reads the cleanup configuration and removes test artifacts
created during test execution by invoking toolkit tools and running
generic processes like pipeline/toolkit deletion.

The cleanup is toolkit-agnostic - it simply invokes specified tools with
specified parameters, making it work with any toolkit type.

Usage:
    python cleanup.py <suite_folder> [options]
    python cleanup.py <suite_folder>:<pipeline_file.yaml> [options]

Examples:
    python cleanup.py github_toolkit
    python cleanup.py github_toolkit_negative:pipeline_validation.yaml
    python cleanup.py github_toolkit --dry-run
    python cleanup.py github_toolkit --skip-pipelines
    python cleanup.py github_toolkit -v

Suite Specification Format:
    - 'suite_name' - Uses default pipeline.yaml in the suite folder
    - 'suite_name:pipeline_file.yaml' - Uses specific pipeline config file
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Optional

import requests
import yaml

from seed_pipelines import (
    DEFAULT_BASE_URL,
    DEFAULT_PROJECT_ID,
)

# Import shared utilities
from utils_common import (
    load_config,
    parse_suite_spec,
    resolve_env_value,
    set_env_file,
    load_from_env,
    load_token_from_env,
    load_base_url_from_env,
    load_project_id_from_env,
)

from delete_pipelines import delete_pipeline, list_pipelines

# Import shared pattern matching utilities
from pattern_matcher import matches_pattern


class CleanupContext:
    """Context for cleanup execution, holds state and environment."""

    def __init__(
        self,
        base_url: str,
        project_id: int,
        bearer_token: str,
        verbose: bool = False,
        dry_run: bool = False,
        quiet: bool = False,
    ):
        self.base_url = base_url
        self.project_id = project_id
        self.bearer_token = bearer_token
        self.verbose = verbose
        self.dry_run = dry_run
        self.quiet = quiet
        self.env_vars: dict[str, Any] = {}
        self.cleanup_stats = {"deleted": 0, "failed": 0, "skipped": 0}

    def get_headers(self, content_type: bool = False) -> dict:
        """Get HTTP headers with authentication."""
        headers = {"Authorization": f"Bearer {self.bearer_token}"}
        if content_type:
            headers["Content-Type"] = "application/json"
        return headers

    def log(self, message: str, level: str = "info"):
        """Log a message if verbose mode is enabled or it's an error/warning."""
        if self.quiet and level not in ("error"):
             return

        if self.verbose:
            prefix = {"info": "  ", "success": "  ✓", "error": "  ✗", "warning": "  ⚠"}
            print(f"{prefix.get(level, '  ')} {message}")
        elif level in ("error", "warning"):
             print(f"{message}")


# =============================================================================
# Cleanup Step Handlers
# =============================================================================


def handle_toolkit_invoke(step: dict, ctx: CleanupContext) -> dict:
    """
    Handle generic toolkit tool invocation for cleanup.

    This is toolkit-agnostic - it simply invokes the specified tool with
    the specified parameters. The config should contain:
      - toolkit_id: The toolkit ID to invoke
      - tool_name: The tool to call
      - tool_params: Parameters to pass to the tool (optional)
      - result_filter: Optional pattern to filter/process results
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


def get_toolkit_by_id(ctx: CleanupContext, toolkit_id: int) -> Optional[dict]:
    """Get toolkit details by ID."""
    url = f"{ctx.base_url}/api/v2/elitea_core/tool/prompt_lib/{ctx.project_id}/{toolkit_id}"
    response = requests.get(url, headers=ctx.get_headers())
    if response.status_code == 200:
        return response.json()
    return None


def invoke_toolkit_tool(ctx: CleanupContext, toolkit_id: int, tool_name: str, params: dict) -> dict:
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
        return {"success": False, "error": response.text[:500]}


def handle_pipeline_cleanup(step: dict, ctx: CleanupContext) -> dict:
    """Handle pipeline deletion cleanup."""
    config = resolve_env_value(step.get("config", {}), ctx.env_vars, env_loader=load_from_env)
    pattern = config.get("pattern")

    ctx.log(f"Pipeline cleanup with pattern: {pattern}")

    if ctx.dry_run:
        # List matching pipelines
        pipelines = list_pipelines(
            ctx.base_url,
            ctx.project_id,
            bearer_token=ctx.bearer_token,
        )
        # Use pattern matching with wildcard support
        matching = [p for p in pipelines if matches_pattern(p.get("name", ""), pattern, use_wildcards=True)]
        ctx.log(f"[DRY RUN] Would delete {len(matching)} pipelines: {[p['name'] for p in matching]}")
        return {"success": True, "dry_run": True, "count": len(matching)}

    # Get pipelines matching pattern
    pipelines = list_pipelines(
        ctx.base_url,
        ctx.project_id,
        bearer_token=ctx.bearer_token,
    )

    if not pipelines:
        ctx.log("No pipelines found", "info")
        return {"success": True, "deleted": 0}

    # Use pattern matching with wildcard support
    matching = [p for p in pipelines if matches_pattern(p.get("name", ""), pattern, use_wildcards=True)]

    if not matching:
        ctx.log(f"No pipelines matching pattern: {pattern}", "info")
        return {"success": True, "deleted": 0}

    deleted = 0
    failed = 0

    for pipeline in matching:
        result = delete_pipeline(
            ctx.base_url,
            ctx.project_id,
            pipeline["id"],
            bearer_token=ctx.bearer_token,
        )
        if result.get("success"):
            ctx.log(f"Deleted: {pipeline['name']} (ID: {pipeline['id']})", "success")
            deleted += 1
        else:
            ctx.log(f"Failed to delete {pipeline['name']}: {result.get('error')}", "error")
            failed += 1

    ctx.cleanup_stats["deleted"] += deleted
    ctx.cleanup_stats["failed"] += failed

    return {"success": failed == 0, "deleted": deleted, "failed": failed}


def handle_toolkit_cleanup(step: dict, ctx: CleanupContext) -> dict:
    """Handle toolkit deletion cleanup."""
    config = resolve_env_value(step.get("config", {}), ctx.env_vars, env_loader=load_from_env)
    toolkit_id = config.get("toolkit_id")

    if not toolkit_id:
        ctx.log("No toolkit_id provided, skipping toolkit cleanup", "warning")
        return {"success": True, "skipped": True}

    ctx.log(f"Toolkit cleanup for ID: {toolkit_id}")

    if ctx.dry_run:
        ctx.log(f"[DRY RUN] Would delete toolkit {toolkit_id}")
        return {"success": True, "dry_run": True}

    url = f"{ctx.base_url}/api/v2/elitea_core/tool/prompt_lib/{ctx.project_id}/{toolkit_id}"
    response = requests.delete(url, headers=ctx.get_headers())

    if response.status_code == 204:
        ctx.log(f"Deleted toolkit {toolkit_id}", "success")
        return {"success": True}
    else:
        ctx.log(f"Failed to delete toolkit: {response.status_code}", "error")
        return {"success": False, "error": response.text[:200]}


def handle_composable_cleanup(config: dict, ctx: CleanupContext) -> dict:
    """Handle cleanup of composable pipelines defined in config.yaml.

    This is automatically invoked based on the composable_pipelines section
    in config.yaml - no explicit cleanup step needed.

    The function resolves the pipeline names (with env substitution) and
    deletes them from the platform.
    """
    composable_pipelines = config.get("composable_pipelines", [])
    if not composable_pipelines:
        return {"success": True, "deleted": 0, "skipped": True, "reason": "no composable pipelines"}

    # Get all pipeline names after env substitution
    pipeline_names = []
    for cp_config in composable_pipelines:
        file_path = cp_config.get("file")
        if not file_path:
            continue

        # Load the composable pipeline file to get its name
        script_dir = Path(__file__).parent
        if file_path.startswith("../"):
            # Resolve from current suite folder context
            yaml_path = None  # We'll use pattern matching instead
        else:
            yaml_path = script_dir / file_path.lstrip("./")

        # Build env for name resolution
        cp_env = {}
        for key, value in cp_config.get("env", {}).items():
            cp_env[key] = resolve_env_value(value, ctx.env_vars, env_loader=load_from_env)

        # Get pipeline name from file or derive from env
        if yaml_path and yaml_path.exists():
            with open(yaml_path) as f:
                cp_data = yaml.safe_load(f)
            name_template = cp_data.get("name", yaml_path.stem)
        else:
            # Use a pattern based on env substitutions
            name_template = cp_config.get("name_pattern", f"*{cp_config.get('env', {}).get('SUITE_NAME', '')}*")

        # Apply env substitutions to name
        resolved_name = name_template
        for var, val in cp_env.items():
            resolved_name = resolved_name.replace(f"${{{var}}}", str(val))
            resolved_name = resolved_name.replace(f"${var}", str(val))

        pipeline_names.append(resolved_name)

    if not pipeline_names:
        return {"success": True, "deleted": 0, "skipped": True, "reason": "no pipeline names resolved"}

    ctx.log(f"Composable pipeline cleanup: {pipeline_names}")

    if ctx.dry_run:
        ctx.log(f"[DRY RUN] Would delete composable pipelines: {pipeline_names}")
        return {"success": True, "dry_run": True, "count": len(pipeline_names)}

    # Get all pipelines and match by name
    pipelines = list_pipelines(
        ctx.base_url,
        ctx.project_id,
        bearer_token=ctx.bearer_token,
    )

    if not pipelines:
        ctx.log("No pipelines found", "info")
        return {"success": True, "deleted": 0}

    # Match pipelines by exact name or pattern
    deleted = 0
    failed = 0

    for target_name in pipeline_names:
        # Use pattern matching with wildcard support
        # matches_pattern will handle both wildcards and flexible substring matching
        use_wildcards = "*" in target_name or "?" in target_name
        matching = [p for p in pipelines if matches_pattern(p.get("name", ""), target_name, use_wildcards=use_wildcards)]

        for pipeline in matching:
            result = delete_pipeline(
                ctx.base_url,
                ctx.project_id,
                pipeline["id"],
                bearer_token=ctx.bearer_token,
            )
            if result.get("success"):
                ctx.log(f"Deleted composable: {pipeline['name']} (ID: {pipeline['id']})", "success")
                deleted += 1
            else:
                ctx.log(f"Failed to delete {pipeline['name']}: {result.get('error')}", "error")
                failed += 1

    ctx.cleanup_stats["deleted"] += deleted
    ctx.cleanup_stats["failed"] += failed

    return {"success": failed == 0, "deleted": deleted, "failed": failed}


# =============================================================================
# Main Cleanup Execution
# =============================================================================


def execute_cleanup(
    config: dict,
    ctx: CleanupContext,
    skip_steps: set[str] = None,
) -> dict:
    """Execute all cleanup steps from config."""
    cleanup_steps = config.get("cleanup", [])
    results = {"success": True, "steps": []}
    skip_steps = skip_steps or set()

    # Count composable pipelines
    composable_count = len(config.get("composable_pipelines", []))

    if not ctx.quiet:
        print(f"\nExecuting cleanup for: {config.get('name', 'unknown')}")
        print(f"Steps: {len(cleanup_steps)}")
        if composable_count > 0:
            print(f"Composable pipelines: {composable_count}")
        print("-" * 60)

    # First, clean up composable pipelines (if not skipped)
    if composable_count > 0 and "composable" not in skip_steps:
        if not ctx.quiet:
            print("\n[0/*] Cleanup Composable Pipelines")
        composable_result = handle_composable_cleanup(config, ctx)
        results["steps"].append({
            "name": "Cleanup Composable Pipelines",
            "type": "composable",
            **composable_result,
        })
        if not composable_result.get("success") and not composable_result.get("dry_run"):
            ctx.log("Some composable pipelines failed to clean up", "warning")

    for i, step in enumerate(cleanup_steps, 1):
        step_name = step.get("name", f"Step {i}")
        step_type = step.get("type")
        action = step.get("action", "")

        if not ctx.quiet:
            print(f"\n[{i}/{len(cleanup_steps)}] {step_name}")

        # Check if step is enabled
        if not step.get("enabled", True):
            ctx.log("Step disabled, skipping", "info")
            results["steps"].append({"name": step_name, "skipped": True, "reason": "disabled"})
            continue

        # Check if step type should be skipped
        if step_type in skip_steps:
            ctx.log(f"Skipping {step_type} steps as requested", "info")
            results["steps"].append({"name": step_name, "skipped": True, "reason": f"--skip-{step_type}"})
            continue

        # Execute step based on type
        step_result = {"success": False, "error": "Unknown step type"}

        try:
            if step_type == "toolkit_invoke":
                # Generic toolkit tool invocation (toolkit-agnostic)
                step_result = handle_toolkit_invoke(step, ctx)
            elif step_type == "pipeline":
                # Platform pipeline deletion
                step_result = handle_pipeline_cleanup(step, ctx)
            elif step_type == "toolkit":
                # Toolkit entity deletion from platform
                step_result = handle_toolkit_cleanup(step, ctx)
            else:
                step_result = {"success": False, "error": f"Unknown step type: {step_type}"}
        except Exception as e:
            step_result = {"success": False, "error": str(e)}

        results["steps"].append({
            "name": step_name,
            "type": step_type,
            "action": action,
            **step_result,
        })

        # Handle failure
        if not step_result.get("success") and not step_result.get("dry_run"):
            if step.get("continue_on_error", True):
                ctx.log(f"Step failed but continuing: {step_result.get('error', 'Unknown error')}", "warning")
            else:
                ctx.log(f"Cleanup failed at step: {step_name}", "error")
                results["success"] = False
                break

    return results

def run(
    folder: str,
    base_url: str | None = None,
    project_id: int | None = None,
    token: str | None = None,
    env_file: str | Path | None = None,
    dry_run: bool = False,
    verbose: bool = False,
    skip_pipelines: bool = False,
    skip_toolkit_invoke: bool = False,
    skip_toolkit: bool = False,
    skip_composable: bool = False,
    quiet: bool = False,
    yes: bool = True
) -> dict:
    """Run cleanup programmatically."""
    # Set custom env file if provided
    if env_file:
        env_file_path = Path(env_file)
        if not env_file_path.exists():
            raise FileNotFoundError(f"Env file not found: {env_file}")
        set_env_file(env_file_path)
        if not quiet:
            print(f"Loading environment from: {env_file}")

    # Parse suite specification and resolve paths
    folder_name, pipeline_file = parse_suite_spec(folder)
    script_dir = Path(__file__).parent
    base_dir = script_dir.parent  # Go up from scripts/ to test_pipelines/
    suite_folder = base_dir / folder_name

    if not suite_folder.exists():
        raise FileNotFoundError(f"Suite folder not found: {suite_folder}")

    # Load configuration
    config = load_config(suite_folder, pipeline_file)

    # Resolve settings
    base_url = base_url or load_base_url_from_env() or DEFAULT_BASE_URL
    project_id = project_id or load_project_id_from_env() or DEFAULT_PROJECT_ID
    bearer_token = token or load_token_from_env()

    if not bearer_token and not dry_run:
        raise ValueError("Authentication token required. Set AUTH_TOKEN or use --token")

    # Build skip set
    skip_steps = set()
    if skip_pipelines:
        skip_steps.add("pipeline")
    if skip_toolkit_invoke:
        skip_steps.add("toolkit_invoke")
    if skip_toolkit:
        skip_steps.add("toolkit")
    if skip_composable:
        skip_steps.add("composable")

    # Create context
    ctx = CleanupContext(
        base_url=base_url,
        project_id=project_id,
        bearer_token=bearer_token or "",
        verbose=verbose,
        dry_run=dry_run,
        quiet=quiet
    )

    # Pre-populate env vars from config's env section if present
    env_config = config.get("env", {})
    for var_name, var_value in env_config.items():
        ctx.env_vars[var_name] = resolve_env_value(var_value, ctx.env_vars, env_loader=load_from_env)

    # Also load any env vars referenced in cleanup steps from actual environment
    cleanup_steps = config.get("cleanup", [])
    for step in cleanup_steps:
        step_config = step.get("config", {})
        for value in step_config.values():
            if isinstance(value, str) and "${" in value:
                # Extract env var names and pre-load them
                for match in re.finditer(r'\$\{([^}:]+)', value):
                    var_name = match.group(1)
                    env_value = load_from_env(var_name)
                    if env_value and var_name not in ctx.env_vars:
                        ctx.env_vars[var_name] = env_value
    
    if not quiet:
        print(f"Cleanup: {config.get('name', folder)}")
        print(f"Target: {base_url} (Project: {project_id})")
        if dry_run:
            print("[DRY RUN MODE]")
        if skip_steps:
            print(f"Skipping: {', '.join(skip_steps)}")
        print("=" * 60)

    # Confirmation
    if not dry_run and not yes:
        confirm = input("\nProceed with cleanup? [y/N]: ")
        if confirm.lower() != "y":
            print("Aborted.")
            sys.exit(0)

    # Execute cleanup
    return execute_cleanup(config, ctx, skip_steps)


def main():
    parser = argparse.ArgumentParser(
        description="Execute cleanup steps from a test suite's config.yaml",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument("folder", help="Suite folder name (e.g., 'github_toolkit')")
    parser.add_argument("--base-url", default=None, help="Platform base URL")
    parser.add_argument("--project-id", type=int, default=None, help="Project ID")
    parser.add_argument("--token", help="Bearer token for authentication")
    parser.add_argument(
        "--env-file",
        help="Load environment variables from a specific file (e.g., .env.generated from setup.py)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without executing")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--skip-pipelines", action="store_true", help="Skip pipeline deletion steps")
    parser.add_argument("--skip-toolkit-invoke", action="store_true", help="Skip toolkit tool invocation steps")
    parser.add_argument("--skip-toolkit", action="store_true", help="Skip toolkit entity deletion steps")
    parser.add_argument("--skip-composable", action="store_true", help="Skip composable pipeline cleanup")
    parser.add_argument("--local", action="store_true", 
                        help="Local mode: skip cleanup (no resources to clean in local mode)")
    parser.add_argument("--json", "-j", action="store_true", help="Output results as JSON")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")

    args = parser.parse_args()

    # In local mode, there are no backend resources to clean up
    if args.local:
        if args.verbose:
            print("[LOCAL MODE] No backend resources to clean up")
        results = {"success": True, "steps": [], "message": "Local mode - no cleanup needed"}
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            print("Local mode - no backend resources to clean up")
        sys.exit(0)

    try:
        results = run(
            folder=args.folder,
            base_url=args.base_url,
            project_id=args.project_id,
            token=args.token,
            env_file=args.env_file,
            dry_run=args.dry_run,
            verbose=args.verbose,
            skip_pipelines=args.skip_pipelines,
            skip_toolkit_invoke=args.skip_toolkit_invoke,
            skip_toolkit=args.skip_toolkit,
            skip_composable=args.skip_composable,
            yes=args.yes,
            quiet=False
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Output results
    print("\n" + "=" * 60)
    print("Cleanup Results")
    print("=" * 60)

    if args.json:
        print(json.dumps(results, indent=2, default=str))
    else: # Re-use the stats from the function return logic if possible, or print from results.
        # But wait, run() returns the results dict.
        # So I need to parse the results dict for display.
        
        # We need to access ctx.cleanup_stats, but ctx is local to run().
        # However, we can re-calculate stats from results['steps']
        stats = {"deleted": 0, "failed": 0, "skipped": 0}
        
        for step in results["steps"]:
            if step.get("skipped"):
                status = "⊘"
                detail = f" ({step.get('reason', 'skipped')})"
                stats["skipped"] += 1
            elif step.get("success"):
                status = "✓"
                detail = ""
                if "deleted" in step:
                    detail = f" (deleted: {step['deleted']})"
                    stats["deleted"] += int(step['deleted'])
            else:
                status = "✗"
                detail = ""
                if step.get("error"):
                    detail = f" ({step['error'][:50]})"
                if "failed" in step:
                    stats["failed"] += int(step.get("failed", 0))
                else:
                    stats["failed"] += 1 # The step itself failed

            print(f"  {status} {step['name']}{detail}")

        print(f"\nSummary:")
        print(f"  Deleted: {stats['deleted']}")
        print(f"  Failed: {stats['failed']}")
        print(f"  Skipped: {stats['skipped']}")

    # Exit with appropriate code
    if not results["success"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
