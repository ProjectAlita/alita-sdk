#!/usr/bin/env python3
"""
Delete pipelines from Elitea platform via REST API.

Usage:
    python delete_pipelines.py --ids 56 57 58 59 60 61 62
    python delete_pipelines.py --range 56-62
    python delete_pipelines.py --pattern "Test Case"

Example:
    python delete_pipelines.py --ids 56 57 58
    python delete_pipelines.py --range 56-62 --project-id 2
"""

import argparse
import sys

import requests

# Import shared utilities
from utils_common import (
    load_token_from_env,
    load_session_from_env,
    load_base_url_from_env,
    load_project_id_from_env,
)

from seed_pipelines import (
    DEFAULT_BASE_URL,
    DEFAULT_PROJECT_ID,
)

# Import shared pattern matching utilities
from pattern_matcher import matches_pattern


def delete_pipeline(
    base_url: str,
    project_id: int,
    application_id: int,
    session_cookie: str = None,
    bearer_token: str = None,
) -> dict:
    """Delete a single pipeline from the platform."""
    url = f"{base_url}/api/v2/elitea_core/application/prompt_lib/{project_id}/{application_id}"

    headers = {}

    # Use Bearer token if provided, otherwise use session cookie
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    elif session_cookie:
        headers["Cookie"] = f"centry_auth_session={session_cookie}"

    response = requests.delete(url, headers=headers)

    if response.status_code == 204:
        return {"success": True}
    else:
        return {
            "success": False,
            "status_code": response.status_code,
            "error": response.text if response.text else "Not found",
        }


def list_pipelines(
    base_url: str,
    project_id: int,
    session_cookie: str = None,
    bearer_token: str = None,
    limit: int = 100,
) -> list:
    """List all pipelines from the platform."""
    url = f"{base_url}/api/v2/elitea_core/applications/prompt_lib/{project_id}"
    params = {
        "agents_type": "pipeline",
        "limit": limit,
        "offset": 0,
        "sort_by": "created_at",
        "sort_order": "desc",
    }

    headers = {}
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    elif session_cookie:
        headers["Cookie"] = f"centry_auth_session={session_cookie}"

    response = requests.get(url, params=params, headers=headers)

    if response.status_code == 200:
        data = response.json()
        return data.get("rows", [])
    return []


def parse_range(range_str: str) -> list[int]:
    """Parse a range string like '56-62' into a list of integers."""
    try:
        start, end = range_str.split("-")
        return list(range(int(start), int(end) + 1))
    except ValueError:
        raise ValueError(f"Invalid range format: {range_str}. Use format: START-END (e.g., 56-62)")


def main():
    parser = argparse.ArgumentParser(
        description="Delete pipelines from Elitea platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s --ids 56 57 58 59
    %(prog)s --range 56-62
    %(prog)s --pattern "Test Case" --dry-run
    %(prog)s --list

Environment Variables:
    AUTH_TOKEN, ELITEA_TOKEN, or API_KEY - Bearer token for authentication
    ELITEA_SESSION - Session cookie for authentication
    BASE_URL or DEPLOYMENT_URL - Platform base URL
        """,
    )

    # Selection options (mutually exclusive)
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--ids",
        nargs="+",
        type=int,
        help="Pipeline IDs to delete",
    )
    group.add_argument(
        "--range",
        dest="id_range",
        help="Range of pipeline IDs to delete (e.g., 56-62)",
    )
    group.add_argument(
        "--pattern",
        help="Delete pipelines matching name pattern (substring match)",
    )
    group.add_argument(
        "--list",
        action="store_true",
        help="List all pipelines (don't delete)",
    )

    # Connection options
    parser.add_argument(
        "--base-url",
        default=None,
        help=f"Base URL of the Elitea platform (default: from BASE_URL env or {DEFAULT_BASE_URL})",
    )
    parser.add_argument(
        "--project-id",
        type=int,
        default=None,
        help=f"Project ID (default: from PROJECT_ID env or {DEFAULT_PROJECT_ID})",
    )
    parser.add_argument(
        "--token",
        help="Bearer token (API key) for authentication",
    )
    parser.add_argument(
        "--session",
        help="Session cookie for authentication",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting",
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip confirmation prompt",
    )

    args = parser.parse_args()

    # Resolve base URL and project ID
    base_url = args.base_url or load_base_url_from_env() or DEFAULT_BASE_URL
    project_id = args.project_id or load_project_id_from_env() or DEFAULT_PROJECT_ID

    # Get authentication credentials
    bearer_token = args.token or load_token_from_env()
    session_cookie = args.session or load_session_from_env()

    if not bearer_token and not session_cookie:
        print("Error: Authentication required. Provide --token or --session", file=sys.stderr)
        sys.exit(1)

    auth_method = "Bearer token" if bearer_token else "Session cookie"

    # Handle --list option
    if args.list:
        print(f"Listing pipelines from {base_url} (Project ID: {project_id})")
        print(f"Auth: {auth_method}")
        print("-" * 60)

        pipelines = list_pipelines(
            base_url, project_id,
            session_cookie=session_cookie,
            bearer_token=bearer_token,
        )

        if not pipelines:
            print("No pipelines found.")
            return

        print(f"{'ID':<6} {'Name':<60}")
        print("-" * 66)
        for p in pipelines:
            print(f"{p['id']:<6} {p['name'][:60]:<60}")
        print(f"\nTotal: {len(pipelines)} pipelines")
        return

    # Determine which IDs to delete
    ids_to_delete = []

    if args.ids:
        ids_to_delete = args.ids
    elif args.id_range:
        ids_to_delete = parse_range(args.id_range)
    elif args.pattern:
        # Fetch pipelines and filter by pattern
        pipelines = list_pipelines(
            base_url, project_id,
            session_cookie=session_cookie,
            bearer_token=bearer_token,
        )
        # Use shared pattern matching utility with wildcard support
        use_wildcards = "*" in args.pattern or "?" in args.pattern
        ids_to_delete = [p["id"] for p in pipelines if matches_pattern(p["name"], args.pattern, use_wildcards=use_wildcards)]

        if not ids_to_delete:
            print(f"No pipelines matching pattern '{args.pattern}' found.")
            sys.exit(0)
    else:
        parser.print_help()
        print("\nError: Must specify --ids, --range, --pattern, or --list", file=sys.stderr)
        sys.exit(1)

    # Show what will be deleted
    print(f"Target: {base_url} (Project ID: {project_id})")
    print(f"Auth: {auth_method}")
    print(f"Pipelines to delete: {len(ids_to_delete)}")
    print(f"IDs: {', '.join(map(str, ids_to_delete))}")
    print("-" * 60)

    if args.dry_run:
        print("[DRY RUN] Would delete the above pipelines")
        sys.exit(0)

    # Confirmation
    if not args.yes:
        confirm = input(f"Delete {len(ids_to_delete)} pipeline(s)? [y/N]: ")
        if confirm.lower() != "y":
            print("Aborted.")
            sys.exit(0)

    # Delete pipelines
    results = {"success": 0, "failed": 0}

    for app_id in ids_to_delete:
        result = delete_pipeline(
            base_url,
            project_id,
            app_id,
            session_cookie=session_cookie,
            bearer_token=bearer_token,
        )

        if result["success"]:
            print(f"  Deleted ID {app_id}")
            results["success"] += 1
        else:
            print(f"  FAILED ID {app_id}: {result.get('error', 'Unknown error')}")
            results["failed"] += 1

    # Summary
    print("\n" + "=" * 60)
    print(f"Summary: {results['success']} deleted, {results['failed']} failed")

    if results["failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
