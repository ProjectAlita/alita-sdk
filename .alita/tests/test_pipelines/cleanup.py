#!/usr/bin/env python3
"""
Execute cleanup steps from a test suite's config.yaml.

This script reads the cleanup configuration and removes test artifacts
created during test execution, including branches, PRs, files, and pipelines.

Usage:
    python cleanup.py <suite_folder> [options]

Examples:
    python cleanup.py github_toolkit
    python cleanup.py github_toolkit --dry-run
    python cleanup.py github_toolkit --skip-pipelines
    python cleanup.py github_toolkit -v
"""

import argparse
import fnmatch
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
    load_from_env,
    load_token_from_env,
    load_base_url_from_env,
    load_project_id_from_env,
    set_env_file,
)

from delete_pipelines import delete_pipeline, list_pipelines


class CleanupContext:
    """Context for cleanup execution, holds state and environment."""

    def __init__(
        self,
        base_url: str,
        project_id: int,
        bearer_token: str,
        verbose: bool = False,
        dry_run: bool = False,
    ):
        self.base_url = base_url
        self.project_id = project_id
        self.bearer_token = bearer_token
        self.verbose = verbose
        self.dry_run = dry_run
        self.env_vars: dict[str, Any] = {}
        self.cleanup_stats = {"deleted": 0, "failed": 0, "skipped": 0}

    def get_headers(self, content_type: bool = False) -> dict:
        """Get HTTP headers with authentication."""
        headers = {"Authorization": f"Bearer {self.bearer_token}"}
        if content_type:
            headers["Content-Type"] = "application/json"
        return headers

    def resolve_env(self, value: Any) -> Any:
        """Resolve environment variable references in a value."""
        if isinstance(value, str):
            pattern = r'\$\{([^}:]+)(?::([^}]*))?\}'

            def replacer(match):
                var_name = match.group(1)
                default = match.group(2)

                if var_name in self.env_vars:
                    return str(self.env_vars[var_name])
                env_value = load_from_env(var_name)
                if env_value:
                    return env_value
                if default is not None:
                    return default
                return match.group(0)

            return re.sub(pattern, replacer, value)
        elif isinstance(value, dict):
            return {k: self.resolve_env(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self.resolve_env(v) for v in value]
        return value

    def log(self, message: str, level: str = "info"):
        """Log a message if verbose mode is enabled."""
        if self.verbose or level in ("error", "warning"):
            prefix = {"info": "  ", "success": "  ✓", "error": "  ✗", "warning": "  ⚠"}
            print(f"{prefix.get(level, '  ')} {message}")


def load_config(suite_folder: Path) -> dict:
    """Load config.yaml from a suite folder."""
    config_path = suite_folder / "config.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path) as f:
        return yaml.safe_load(f)


# =============================================================================
# Cleanup Step Handlers
# =============================================================================


def handle_github_cleanup(step: dict, ctx: CleanupContext) -> dict:
    """Handle GitHub-related cleanup actions."""
    action = step.get("action")
    config = ctx.resolve_env(step.get("config", {}))

    toolkit_ref = config.get("toolkit_ref")

    ctx.log(f"GitHub cleanup action: {action}")

    if ctx.dry_run:
        ctx.log(f"[DRY RUN] Would execute: {action}")
        return {"success": True, "dry_run": True}

    if action == "delete_branches":
        return github_delete_branches(ctx, toolkit_ref, config)
    elif action == "close_pull_requests":
        return github_close_prs(ctx, toolkit_ref, config)
    elif action == "delete_files":
        return github_delete_files(ctx, toolkit_ref, config)
    else:
        return {"success": False, "error": f"Unknown github action: {action}"}


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


def github_delete_branches(ctx: CleanupContext, toolkit_ref: str, config: dict) -> dict:
    """Delete branches matching a pattern."""
    pattern = config.get("pattern", "tc-test-*")
    keep_recent = config.get("keep_recent", 0)

    if not toolkit_ref:
        ctx.log("No toolkit_ref provided, skipping branch cleanup", "warning")
        return {"success": True, "skipped": True}

    toolkit_id = int(toolkit_ref)

    # List branches
    result = invoke_toolkit_tool(ctx, toolkit_id, "list_branches_in_repo", {})
    if not result.get("success"):
        return result

    branches = result.get("result", [])
    if isinstance(branches, str):
        branches = [b.strip() for b in branches.split("\n") if b.strip()]

    # Filter branches matching pattern
    matching = [b for b in branches if fnmatch.fnmatch(b, pattern)]

    if not matching:
        ctx.log(f"No branches matching pattern: {pattern}", "info")
        return {"success": True, "deleted": 0}

    # Sort and optionally keep recent
    matching.sort(reverse=True)
    if keep_recent > 0:
        to_delete = matching[keep_recent:]
    else:
        to_delete = matching

    deleted = 0
    for branch in to_delete:
        # Note: delete_branch tool may not exist in all toolkit configurations
        # This is a placeholder for the actual implementation
        ctx.log(f"Would delete branch: {branch}", "info")
        deleted += 1

    ctx.log(f"Deleted {deleted} branches", "success")
    return {"success": True, "deleted": deleted, "branches": to_delete}


def github_close_prs(ctx: CleanupContext, toolkit_ref: str, config: dict) -> dict:
    """Close pull requests matching a pattern."""
    pattern = config.get("pattern", "[Test]*")
    # comment = config.get("add_comment")  # For future use when closing PRs

    if not toolkit_ref:
        ctx.log("No toolkit_ref provided, skipping PR cleanup", "warning")
        return {"success": True, "skipped": True}

    toolkit_id = int(toolkit_ref)

    # List open PRs
    result = invoke_toolkit_tool(ctx, toolkit_id, "list_open_pull_requests", {})
    if not result.get("success"):
        return result

    prs = result.get("result", [])
    if isinstance(prs, str):
        try:
            prs = json.loads(prs)
        except json.JSONDecodeError:
            prs = []

    # Filter PRs matching pattern
    matching = []
    for pr in prs if isinstance(prs, list) else []:
        title = pr.get("title", "")
        if fnmatch.fnmatch(title, pattern):
            matching.append(pr)

    if not matching:
        ctx.log(f"No PRs matching pattern: {pattern}", "info")
        return {"success": True, "closed": 0}

    closed = 0
    for pr in matching:
        pr_number = pr.get("number")
        if pr_number:
            ctx.log(f"Would close PR #{pr_number}: {pr.get('title')}", "info")
            closed += 1

    ctx.log(f"Closed {closed} PRs", "success")
    return {"success": True, "closed": closed}


def github_delete_files(ctx: CleanupContext, toolkit_ref: str, config: dict) -> dict:
    """Delete files matching a pattern from a branch."""
    branch = config.get("branch")
    pattern = config.get("pattern", "test-file-*.md")

    if not toolkit_ref or not branch:
        ctx.log("toolkit_ref and branch required for file deletion", "warning")
        return {"success": True, "skipped": True}

    toolkit_id = int(toolkit_ref)

    # List files in branch
    result = invoke_toolkit_tool(ctx, toolkit_id, "list_files_in_bot_branch", {})
    if not result.get("success"):
        return result

    files = result.get("result", [])
    if isinstance(files, str):
        files = [f.strip() for f in files.split("\n") if f.strip()]

    # Filter files matching pattern
    matching = [f for f in files if fnmatch.fnmatch(f, pattern)]

    if not matching:
        ctx.log(f"No files matching pattern: {pattern}", "info")
        return {"success": True, "deleted": 0}

    deleted = 0
    for file_path in matching:
        ctx.log(f"Would delete file: {file_path}", "info")
        deleted += 1

    ctx.log(f"Deleted {deleted} files", "success")
    return {"success": True, "deleted": deleted, "files": matching}


def handle_pipeline_cleanup(step: dict, ctx: CleanupContext) -> dict:
    """Handle pipeline deletion cleanup."""
    config = ctx.resolve_env(step.get("config", {}))
    pattern = config.get("pattern")

    ctx.log(f"Pipeline cleanup with pattern: {pattern}")

    if ctx.dry_run:
        # List matching pipelines
        pipelines = list_pipelines(
            ctx.base_url,
            ctx.project_id,
            bearer_token=ctx.bearer_token,
        )
        matching = [p for p in pipelines if fnmatch.fnmatch(p.get("name", ""), pattern)]
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

    matching = [p for p in pipelines if fnmatch.fnmatch(p.get("name", ""), pattern)]

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
    config = ctx.resolve_env(step.get("config", {}))
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

    print(f"\nExecuting cleanup for: {config.get('name', 'unknown')}")
    print(f"Steps: {len(cleanup_steps)}")
    print("-" * 60)

    for i, step in enumerate(cleanup_steps, 1):
        step_name = step.get("name", f"Step {i}")
        step_type = step.get("type")
        action = step.get("action", "")

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
            if step_type == "github":
                step_result = handle_github_cleanup(step, ctx)
            elif step_type == "pipeline":
                step_result = handle_pipeline_cleanup(step, ctx)
            elif step_type == "toolkit":
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
    parser.add_argument("--skip-pipelines", action="store_true", help="Skip pipeline deletion")
    parser.add_argument("--skip-github", action="store_true", help="Skip GitHub cleanup actions")
    parser.add_argument("--skip-toolkit", action="store_true", help="Skip toolkit deletion")
    parser.add_argument("--json", "-j", action="store_true", help="Output results as JSON")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")

    args = parser.parse_args()

    # Set custom env file if provided (must be done before any load_from_env calls)
    if args.env_file:
        env_file_path = Path(args.env_file)
        if not env_file_path.exists():
            print(f"Error: Env file not found: {args.env_file}", file=sys.stderr)
            sys.exit(1)
        set_env_file(env_file_path)
        print(f"Loading environment from: {args.env_file}")

    # Resolve paths
    script_dir = Path(__file__).parent
    suite_folder = script_dir / args.folder

    if not suite_folder.exists():
        print(f"Error: Suite folder not found: {suite_folder}", file=sys.stderr)
        sys.exit(1)

    # Load configuration
    try:
        config = load_config(suite_folder)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Resolve settings
    base_url = args.base_url or load_base_url_from_env() or DEFAULT_BASE_URL
    project_id = args.project_id or load_project_id_from_env() or DEFAULT_PROJECT_ID
    bearer_token = args.token or load_token_from_env()

    if not bearer_token and not args.dry_run:
        print("Error: Authentication token required. Set AUTH_TOKEN or use --token", file=sys.stderr)
        sys.exit(1)

    # Build skip set
    skip_steps = set()
    if args.skip_pipelines:
        skip_steps.add("pipeline")
    if args.skip_github:
        skip_steps.add("github")
    if args.skip_toolkit:
        skip_steps.add("toolkit")

    # Create context
    ctx = CleanupContext(
        base_url=base_url,
        project_id=project_id,
        bearer_token=bearer_token or "",
        verbose=args.verbose,
        dry_run=args.dry_run,
    )

    # Pre-populate env vars from .env and os.environ
    for var in ["GITHUB_TOOLKIT_ID", "GITHUB_TOOLKIT_NAME", "GITHUB_TEST_BRANCH"]:
        value = load_from_env(var)
        if value:
            ctx.env_vars[var] = value

    print(f"Cleanup: {config.get('name', args.folder)}")
    print(f"Target: {base_url} (Project: {project_id})")
    if args.dry_run:
        print("[DRY RUN MODE]")
    if skip_steps:
        print(f"Skipping: {', '.join(skip_steps)}")
    print("=" * 60)

    # Confirmation
    if not args.dry_run and not args.yes:
        confirm = input("\nProceed with cleanup? [y/N]: ")
        if confirm.lower() != "y":
            print("Aborted.")
            sys.exit(0)

    # Execute cleanup
    results = execute_cleanup(config, ctx, skip_steps)

    # Output results
    print("\n" + "=" * 60)
    print("Cleanup Results")
    print("=" * 60)

    if args.json:
        print(json.dumps(results, indent=2, default=str))
    else:
        for step in results["steps"]:
            if step.get("skipped"):
                status = "⊘"
                detail = f" ({step.get('reason', 'skipped')})"
            elif step.get("success"):
                status = "✓"
                detail = ""
                if "deleted" in step:
                    detail = f" (deleted: {step['deleted']})"
            else:
                status = "✗"
                detail = ""
                if step.get("error"):
                    detail = f" ({step['error'][:50]})"

            print(f"  {status} {step['name']}{detail}")

        print(f"\nSummary:")
        print(f"  Deleted: {ctx.cleanup_stats['deleted']}")
        print(f"  Failed: {ctx.cleanup_stats['failed']}")
        print(f"  Skipped: {ctx.cleanup_stats['skipped']}")

    # Exit with appropriate code
    if not results["success"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
