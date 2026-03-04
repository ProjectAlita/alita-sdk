#!/usr/bin/env python3
"""
Link nested applications to parent applications on target, mirroring the source.

Steps:
  1. Fetch all apps from target (source of truth)
  2. Fetch all apps from source — keep only those present on target
  3. For each matched app: get source details → version_details.tools;
     for each application-type tool, find on target by name and PATCH link via
     application_relation endpoint.

Setup (use a virtual environment; the only dependency is "requests"):

    pip install requests

Usage:

    python link_apps.py \\
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


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    # CLI: source/target env, project IDs, tokens
    env_names = ", ".join(ENV_URLS)
    parser = argparse.ArgumentParser(
        description="Link nested applications to parent apps on target, mirroring source.",
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

    # Target apps = source of truth (name -> app id)
    target_apps = target.list_apps()
    target_app_map: dict[str, int] = {
        app["name"]: app["id"]
        for app in target_apps
        if app.get("name")
    }
    log.info("Target apps: %d", len(target_app_map))

    # Only process source apps that exist on target; one entry per app name (deduplicate)
    source_apps = source.list_apps()
    matched_all = [a for a in source_apps if a.get("name") in target_app_map]
    seen_names: set[str] = set()
    matched: list[dict] = []
    for a in matched_all:
        name = a.get("name")
        if name and name not in seen_names:
            seen_names.add(name)
            matched.append(a)
    log.info("Source apps matched on target: %d / %d", len(matched), len(source_apps))

    linked = 0
    skipped = 0
    already_linked = 0
    errors: list[str] = []

    for src_app in matched:
        app_name = src_app["name"]

        # Source app details and its tools (only type=application - nested apps)
        src_details = source.get_app_details(src_app["id"])
        if not src_details:
            errors.append(f"{app_name}: failed to fetch source details")
            log.warning("  %s: failed to fetch source details", app_name)
            continue

        ver = src_details.get("version_details") or {}
        src_tools = ver.get("tools") or []
        if not src_tools:
            continue

        app_tools = [t for t in src_tools if t.get("type") == "application"]
        if not app_tools:
            continue

        # Target parent app and its version; collect already-linked nested app ids to skip relink
        tgt_app_id = target_app_map[app_name]
        tgt_details = target.get_app_details(tgt_app_id)
        if not tgt_details:
            errors.append(f"{app_name}: failed to fetch target details")
            log.warning("  %s: failed to fetch target details — skipping", app_name)
            continue
        tgt_versions = tgt_details.get("versions") or []
        if not tgt_versions:
            errors.append(f"{app_name}: no version on target")
            log.warning("  %s: no version on target — skipping", app_name)
            continue
        tgt_version_id = tgt_versions[0]["id"]

        # Collect tools: prefer version-specific list if API returns it, else version_details.tools
        tgt_tools = (tgt_details.get("version_details") or {}).get("tools") or []
        version_for_id = next((v for v in tgt_versions if v.get("id") == tgt_version_id), None)
        if version_for_id and version_for_id.get("tools"):
            tgt_tools = version_for_id.get("tools")
        # Already-linked application ids (check common response shapes: settings.application_id, top-level application_id/entity_id)
        already_linked_app_ids = set()
        for t in tgt_tools:
            if t.get("type") != "application":
                continue
            app_id = (t.get("settings") or {}).get("application_id") or t.get("application_id") or t.get("entity_id")
            if app_id is not None:
                already_linked_app_ids.add(app_id)

        log.info("  %s (target id=%d, ver=%d) — %d nested app(s):",
                 app_name, tgt_app_id, tgt_version_id, len(app_tools))

        for tool in app_tools:
            tool_name = tool.get("name") or ""
            label = f"[app] {tool_name}"

            # Resolve nested app on target by name
            nested_app_id = target_app_map.get(tool_name)
            if nested_app_id is None:
                skipped += 1
                log.info("    %s — not found on target, skipped", label)
                continue

            if nested_app_id in already_linked_app_ids:
                already_linked += 1
                log.info("    %s — already linked, skip", label)
                continue

            # Nested app version id required for PATCH payload
            nested_details = target.get_app_details(nested_app_id)
            if not nested_details:
                errors.append(f"{app_name} -> {label}: failed to fetch nested app details")
                log.warning("    %s: failed to fetch nested app details", label)
                continue
            nested_versions = nested_details.get("versions") or []
            if not nested_versions:
                errors.append(f"{app_name} -> {label}: nested app has no version")
                log.warning("    %s: nested app has no version", label)
                continue
            nested_version_id = nested_versions[0]["id"]

            result = target.link_app(
                tgt_app_id, tgt_version_id, nested_app_id, nested_version_id
            )
            if result.get("success"):
                linked += 1
                log.info("    %s — linked", label)
            else:
                err = result.get("error", "")
                err_str = err if isinstance(err, str) else str(err)
                if "already exists relation" in err_str.lower():
                    already_linked += 1
                    log.info("    %s — already linked (API), skip", label)
                else:
                    errors.append(f"{app_name} -> {label}: {err}")
                    log.warning("    %s: %s", label, err)

    log.info("\n--- Summary ---")
    log.info("  Linked: %d", linked)
    log.info("  Already linked (skipped): %d", already_linked)
    log.info("  Skipped (not on target): %d", skipped)
    log.info("  Errors: %d", len(errors))
    if errors:
        for e in errors:
            log.info("    - %s", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
