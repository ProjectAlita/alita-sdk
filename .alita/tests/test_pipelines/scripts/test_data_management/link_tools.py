#!/usr/bin/env python3
"""
Link toolkits and MCPs to applications on target, mirroring the source environment.

Steps:
  1. Fetch all apps from target (source of truth)
  2. Fetch all apps from source — keep only those present on target
  3. Fetch target toolkits and target MCPs; merge into one name→id map
  4. For each matched app: get source details → version_details.tools;
     for each non-application tool, find on target by toolkit_name and PATCH link.
     Summary splits "not found" by toolkits vs MCPs.

Setup (use a virtual environment; the only dependency is "requests"):

    pip install requests

Usage:

    python link_tools.py \\
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

_YELLOW = "\033[33m"
_RESET = "\033[0m"


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    env_names = ", ".join(ENV_URLS)
    parser = argparse.ArgumentParser(
        description="Link toolkits and MCPs to applications on target, mirroring source.",
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

    target_apps = target.list_apps()
    target_app_map: dict[str, int] = {
        app["name"]: app["id"]
        for app in target_apps
        if app.get("name")
    }
    log.info("Target apps: %d", len(target_app_map))

    source_apps = source.list_apps()
    matched = [a for a in source_apps if a.get("name") in target_app_map]
    log.info("Source apps matched on target: %d / %d", len(matched), len(source_apps))

    source_mcp_names: set[str] = {
        m["toolkit_name"] for m in source.list_mcp()
        if m.get("toolkit_name")
    }
    target_toolkits = target.list_toolkits()
    target_toolkit_map: dict[str, int] = {
        t["toolkit_name"]: t["id"]
        for t in target_toolkits
        if t.get("toolkit_name")
    }
    target_mcps = target.list_mcp()
    target_mcp_map: dict[str, int] = {
        m["toolkit_name"]: m["id"]
        for m in target_mcps
        if m.get("toolkit_name")
    }
    target_tool_map: dict[str, int] = {**target_toolkit_map, **target_mcp_map}
    log.info("Target toolkits: %d, MCPs: %d (combined: %d)", len(target_toolkit_map), len(target_mcp_map), len(target_tool_map))

    linked = 0
    skipped = 0
    already_linked = 0
    errors: list[str] = []
    not_found_toolkits: set[str] = set()
    not_found_mcps: set[str] = set()

    for src_app in matched:
        app_name = src_app["name"]

        src_details = source.get_app_details(src_app["id"])
        if not src_details:
            errors.append(f"{app_name}: failed to fetch source details")
            log.warning("  %s: failed to fetch source details", app_name)
            continue

        ver = src_details.get("version_details") or {}
        src_tools = ver.get("tools") or []
        if not src_tools:
            continue

        tgt_app_id = target_app_map[app_name]
        tgt_details = target.get_app_details(tgt_app_id)
        if not tgt_details:
            errors.append(f"{app_name}: failed to fetch target details")
            log.warning("  %s: failed to fetch target details", app_name)
            continue
        tgt_versions = tgt_details.get("versions") or []
        if not tgt_versions:
            errors.append(f"{app_name}: no version on target")
            log.warning("  %s: no version on target", app_name)
            continue
        tgt_version_id = tgt_versions[0]["id"]

        tools_to_link = [t for t in src_tools if t.get("type") != "application"]
        if not tools_to_link:
            continue

        tgt_tools = (tgt_details.get("version_details") or {}).get("tools") or []
        already_linked_names = {
            t.get("toolkit_name") for t in tgt_tools
            if t.get("toolkit_name")
        }

        log.info("  %s (target id=%d, ver=%d) — %d tool(s):",
                 app_name, tgt_app_id, tgt_version_id, len(tools_to_link))

        for tool in tools_to_link:
            toolkit_name = tool.get("toolkit_name") or ""
            is_mcp = toolkit_name in source_mcp_names
            label = f"[mcp] {tool.get('name') or toolkit_name}" if is_mcp else f"[toolkit] {tool.get('name') or toolkit_name}"

            tgt_tool_id = target_tool_map.get(toolkit_name)
            if tgt_tool_id is None:
                skipped += 1
                if is_mcp:
                    not_found_mcps.add(toolkit_name)
                else:
                    not_found_toolkits.add(toolkit_name)
                log.info("    %s — not found on target, skipped", label)
                continue

            if toolkit_name in already_linked_names:
                already_linked += 1
                log.info("    %s — already linked, skip", label)
                continue

            result = target.link_tool(tgt_tool_id, tgt_app_id, tgt_version_id)
            if result.get("success"):
                linked += 1
                log.info("    %s — linked", label)
            else:
                err = result.get("error", result)
                errors.append(f"{app_name} -> {label}: {err}")
                log.warning("    %s: %s", label, err)

    log.info("\n--- Summary ---")
    log.info("  Linked: %d", linked)
    log.info("  Already linked (skipped): %d", already_linked)
    log.info("  Skipped (not on target): %d", skipped)
    log.info("  Errors: %d", len(errors))
    if not_found_toolkits:
        log.info("  %sToolkits not found on target: %s%s", _YELLOW, ", ".join(sorted(not_found_toolkits)), _RESET)
    if not_found_mcps:
        log.info("  %sMCPs not found on target: %s%s", _YELLOW, ", ".join(sorted(not_found_mcps)), _RESET)
    if errors:
        for e in errors:
            log.info("    - %s", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
