#!/usr/bin/env python3
"""
CI Cleanup Script - Remove uncleaned test data from Elitea platform.

Removes:
  - All pipelines that have the tag "automation"
  - All toolkits whose name contains the word "testing" (case-insensitive)

Usage:
    python ci_cleanup.py [options]

Examples:
    python ci_cleanup.py --yes
    python ci_cleanup.py --dry-run
    python ci_cleanup.py --pipelines-only
    python ci_cleanup.py --toolkits-only
    python ci_cleanup.py --pipeline-tag automation --toolkit-keyword testing

Environment Variables:
    AUTH_TOKEN, ELITEA_TOKEN, or API_KEY  - Bearer token
    BASE_URL or DEPLOYMENT_URL            - Platform base URL
    PROJECT_ID                            - Project ID
"""

import argparse
import sys
import os
from pathlib import Path

import requests

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except AttributeError:
    pass
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

_SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(_SCRIPT_DIR))

from seed_pipelines import DEFAULT_BASE_URL, DEFAULT_PROJECT_ID
from utils_common import load_token_from_env, load_base_url_from_env, load_project_id_from_env


# ---------------------------------------------------------------------------
# Generic paginated list + delete helpers
# ---------------------------------------------------------------------------

def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _paginate(url: str, token: str, batch: int = 200, extra_params: dict = None) -> list:
    """Fetch all rows from a paginated Elitea list endpoint."""
    rows, offset = [], 0
    params = {**(extra_params or {}), "limit": batch}
    while True:
        params["offset"] = offset
        resp = requests.get(url, params=params, headers=_auth(token))
        if resp.status_code != 200:
            print(f"  ERROR listing {url} (HTTP {resp.status_code}): {resp.text[:200]}", file=sys.stderr)
            break
        page = resp.json().get("rows", [])
        rows.extend(page)
        if len(page) < batch:
            break
        offset += batch
    return rows


def _run_cleanup(label: str, items: list, delete_url_fn, token: str, dry_run: bool, verbose: bool = False) -> dict:
    """Generic delete loop shared by pipelines and toolkits."""
    deleted = failed = 0
    for item in items:
        iid  = item["id"]
        name = item.get("name", f"<id:{iid}>")
        if dry_run:
            print(f"  [DRY RUN] Would delete {label}: '{name}' (ID: {iid})")
            continue
        ok = requests.delete(delete_url_fn(item), headers=_auth(token)).status_code == 204
        if ok:
            if verbose:
                print(f"  Deleted {label}: '{name}' (ID: {iid})")
            deleted += 1
        else:
            print(f"  FAILED  {label}: '{name}' (ID: {iid})", file=sys.stderr)
            failed += 1
    return {"deleted": deleted, "failed": failed}


# ---------------------------------------------------------------------------
# Pipeline cleanup
# ---------------------------------------------------------------------------

def _has_tag(pipeline: dict, tag: str) -> bool:
    tag_lower = tag.lower()
    for t in pipeline.get("tags", []):
        if isinstance(t, dict) and str(t.get("name", "")).lower() == tag_lower:
            return True
        if isinstance(t, str) and t.lower() == tag_lower:
            return True
    return False


def cleanup_pipelines(base_url, project_id, token, tag, dry_run, verbose=False) -> dict:
    print(f"\n[Pipelines] tag = '{tag}'")
    all_items = _paginate(
        f"{base_url}/api/v2/elitea_core/applications/prompt_lib/{project_id}",
        token,
        extra_params={"agents_type": "pipeline", "sort_by": "created_at", "sort_order": "desc"},
    )
    matching = [p for p in all_items if _has_tag(p, tag)]
    print(f"  Total: {len(all_items)}  |  Matching: {len(matching)}")
    return _run_cleanup(
        "pipeline", matching,
        lambda p: f"{base_url}/api/v2/elitea_core/application/prompt_lib/{project_id}/{p['id']}",
        token, dry_run, verbose=verbose,
    )


# ---------------------------------------------------------------------------
# Toolkit cleanup
# ---------------------------------------------------------------------------

def cleanup_toolkits(base_url, project_id, token, keyword, dry_run, verbose=False) -> dict:
    print(f"\n[Toolkits] name contains '{keyword}'")
    all_items = _paginate(
        f"{base_url}/api/v2/elitea_core/tools/prompt_lib/{project_id}",
        token, batch=500,
    )
    kw = keyword.lower()
    matching = [t for t in all_items if kw in t.get("name", "").lower()]
    print(f"  Total: {len(all_items)}  |  Matching: {len(matching)}")
    return _run_cleanup(
        "toolkit", matching,
        lambda t: f"{base_url}/api/v2/elitea_core/tool/prompt_lib/{project_id}/{t['id']}",
        token, dry_run, verbose=verbose,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="CI cleanup: remove pipelines by tag and toolkits by name keyword",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --yes
  %(prog)s --dry-run
  %(prog)s --pipelines-only
  %(prog)s --toolkits-only
  %(prog)s --pipeline-tag automation --toolkit-keyword testing
        """,
    )

    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--pipelines-only", action="store_true", help="Skip toolkit cleanup")
    scope.add_argument("--toolkits-only",  action="store_true", help="Skip pipeline cleanup")

    parser.add_argument("--pipeline-tag",    default="automation", metavar="TAG",     help="Pipeline tag to match (default: automation)")
    parser.add_argument("--toolkit-keyword", default="testing",    metavar="KEYWORD", help="Toolkit name substring to match (default: testing)")
    parser.add_argument("--base-url",   default=None,      help="Platform base URL")
    parser.add_argument("--project-id", default=None, type=int, help="Project ID")
    parser.add_argument("--token",      default=None,      help="Bearer token / API key")
    parser.add_argument("--dry-run",    action="store_true", help="List targets without deleting")
    parser.add_argument("--yes", "-y",  action="store_true", help="Skip confirmation (required for CI)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")

    args = parser.parse_args()

    base_url   = args.base_url   or load_base_url_from_env()   or DEFAULT_BASE_URL
    project_id = args.project_id or load_project_id_from_env() or DEFAULT_PROJECT_ID
    token      = args.token      or load_token_from_env()

    if not token:
        print("ERROR: No token. Set AUTH_TOKEN / ELITEA_TOKEN / API_KEY or pass --token.", file=sys.stderr)
        return 1

    print("=" * 60)
    print("  Elitea CI Cleanup")
    print("=" * 60)
    print(f"  URL     : {base_url}")
    print(f"  Project : {project_id}")
    if not args.toolkits_only:
        print(f"  Pipelines with tag    : '{args.pipeline_tag}'")
    if not args.pipelines_only:
        print(f"  Toolkits with keyword : '{args.toolkit_keyword}'")
    if args.dry_run:
        print("  Mode    : DRY RUN")
    print("=" * 60)

    if not args.dry_run and not args.yes:
        if input("\nProceed with deletion? [y/N]: ").strip().lower() != "y":
            print("Aborted.")
            return 0

    total_deleted = total_failed = 0

    if not args.toolkits_only:
        s = cleanup_pipelines(base_url, project_id, token, args.pipeline_tag,    args.dry_run, verbose=args.verbose)
        total_deleted += s["deleted"]; total_failed += s["failed"]

    if not args.pipelines_only:
        s = cleanup_toolkits(base_url, project_id, token, args.toolkit_keyword, args.dry_run, verbose=args.verbose)
        total_deleted += s["deleted"]; total_failed += s["failed"]

    print("\n" + "=" * 60)
    if args.dry_run:
        print("  DRY RUN complete – no changes made.")
    else:
        print(f"  Done: {total_deleted} deleted, {total_failed} failed.")
    print("=" * 60)

    return 1 if total_failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())

