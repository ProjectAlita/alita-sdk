#!/usr/bin/env python3
"""
Copy MCP toolkits from source Alita environment to target.

Steps:
  1. List all MCPs from the source project (GET tools with mcp=true)
  2. List all MCPs from the target project
  3. Compare by toolkit_name — identify MCPs that exist on source but not target
  4. Create the missing MCPs on the target (POST one by one)

Setup (use a virtual environment; the only dependency is "requests"):

    pip install requests

Usage:

    python copy_mcps.py \\
        --source-env next --source-project-id 471 --source-token TOKEN \\
        --target-env stage --target-project-id 52 --target-token TOKEN

Environments: dev, stage, next. URLs are resolved automatically.
"""

from __future__ import annotations

import argparse
import logging
import sys

from alita_api_common import ENV_URLS, AlitaAPI

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except AttributeError:
    pass

log = logging.getLogger(__name__)


def build_mcp_payload(mcp: dict) -> dict:
    """Build a POST payload for creating an MCP on the target.

    Maps type, name, description, settings, meta from source list item.
    """
    return {
        "type": mcp.get("type", "mcp"),
        "name": mcp.get("name", ""),
        "description": mcp.get("description"),
        "settings": mcp.get("settings"),
        "meta": mcp.get("meta"),
    }


def main() -> int:
    """Parse CLI args, run the copy flow, print summary."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    env_names = ", ".join(ENV_URLS)
    parser = argparse.ArgumentParser(
        description="Copy MCP toolkits from source to target.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--source-env",        required=True, choices=ENV_URLS, help=f"Source environment ({env_names})")
    parser.add_argument("--source-project-id", required=True, type=int,         help="Source project ID")
    parser.add_argument("--source-token",      required=True,                   help="Source bearer token")
    parser.add_argument("--target-env",        required=True, choices=ENV_URLS, help=f"Target environment ({env_names})")
    parser.add_argument("--target-project-id", required=True, type=int,         help="Target project ID")
    parser.add_argument("--target-token",      required=True,                   help="Target bearer token")
    args = parser.parse_args()

    source = AlitaAPI(ENV_URLS[args.source_env], args.source_project_id, args.source_token)
    target = AlitaAPI(ENV_URLS[args.target_env], args.target_project_id, args.target_token)

    log.info("Source: %s (%s) project=%d", args.source_env, source.base_url, source.project_id)
    log.info("Target: %s (%s) project=%d", args.target_env, target.base_url, target.project_id)

    # Step 1: List all MCPs from source
    source_mcps = source.list_mcp()
    log.info("Source MCPs: %d", len(source_mcps))

    # Step 2: List all MCPs from target
    target_mcps = target.list_mcp()
    log.info("Target MCPs: %d", len(target_mcps))

    # Step 3: Compare by toolkit_name — find MCPs missing on target
    target_names: set[str] = {m.get("toolkit_name") for m in target_mcps if m.get("toolkit_name")}
    to_copy = [
        m for m in source_mcps
        if m.get("toolkit_name") and m["toolkit_name"] not in target_names
    ]

    log.info("MCPs to copy: %d (missing on target)", len(to_copy))
    for m in to_copy:
        log.info("  - %s (type=%s, name=%s)", m["toolkit_name"], m.get("type"), m.get("name", ""))

    if not to_copy:
        log.info("Nothing to copy.")
        return 0

    # Step 4: Create missing MCPs on target one by one
    errors: list[str] = []
    copied = 0

    for mcp in to_copy:
        mcp_name = mcp["toolkit_name"]
        payload = build_mcp_payload(mcp)

        log.info("  Creating: %s (type=%s) ...", mcp_name, mcp.get("type"))
        result = target.create_tool(payload)
        if result.get("success"):
            new_id = result["data"].get("id")
            log.info("    -> target id=%s", new_id)
            copied += 1
        else:
            err = result.get("error", "")
            errors.append(f"{mcp_name}: {err}")
            log.warning("  %s: %s", mcp_name, err)

    # Summary
    log.info("\n--- Summary ---")
    log.info("  MCPs copied: %d / %d", copied, len(to_copy))
    log.info("  Errors: %d", len(errors))
    if errors:
        for e in errors:
            log.info("    - %s", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
