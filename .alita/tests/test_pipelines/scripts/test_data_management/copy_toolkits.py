#!/usr/bin/env python3
"""
Copy toolkits from source Alita environment to target.

Steps:
  1. List all toolkits from the source project
  2. List all toolkits from the target project
  3. Compare by toolkit_name — identify toolkits that exist on source but not target
  4. Create the missing toolkits on the target

Setup (use a virtual environment; the only dependency is "requests"):

    pip install requests

Usage:

    python copy_toolkits.py \\
        --source-env next --source-project-id 471 --source-token TOKEN \\
        --target-env stage --target-project-id 52 --target-token TOKEN

Environments: dev, stage, next. URLs are resolved automatically.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys

from alita_api_common import ENV_URLS, AlitaAPI

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except AttributeError:
    pass

log = logging.getLogger(__name__)

# ANSI: yellow for "not allowed anymore" summary section
_YELLOW = "\033[33m"
_RESET = "\033[0m"

# Regex to extract allowed tool names from API error msg: "Input should be 'a', 'b', ... or 'c'"
_ALLOWED_TOOLS_RE = re.compile(r"'([^']+)'")


def _parse_allowed_tools_from_error(error: str | list | dict) -> list[str]:
    """Extract the list of allowed tool names from API validation error message."""
    msg = ""
    if isinstance(error, str):
        try:
            data = json.loads(error)
        except (json.JSONDecodeError, TypeError):
            data = None
        if isinstance(data, dict):
            items = data.get("error", data.get("errors", []))
            if isinstance(items, list) and items and isinstance(items[0], dict):
                msg = items[0].get("msg", "")
        if not msg:
            msg = error
    elif isinstance(error, list) and error and isinstance(error[0], dict):
        msg = error[0].get("msg", "")
    elif isinstance(error, dict):
        items = error.get("error", error.get("errors", []))
        if isinstance(items, list) and items and isinstance(items[0], dict):
            msg = items[0].get("msg", "")
    return _ALLOWED_TOOLS_RE.findall(msg) if msg else []


def _selected_tools_diff(payload: dict, error: str | list | dict) -> tuple[list[str], list[str]]:
    """Compare sent selected_tools with allowed tools from error. Returns (invalid, allowed)."""
    sent = (payload.get("settings") or {}).get("selected_tools") or []
    allowed = _parse_allowed_tools_from_error(error)
    allowed_set = set(allowed)
    invalid = [t for t in sent if t not in allowed_set]
    return invalid, allowed


def _payload_with_allowed_tools_only(payload: dict, allowed: list[str]) -> dict:
    """Return a copy of payload with settings.selected_tools restricted to allowed list."""
    allowed_set = set(allowed)
    settings = dict((payload.get("settings") or {}))
    sent = settings.get("selected_tools") or []
    settings["selected_tools"] = [t for t in sent if t in allowed_set]
    return {**payload, "settings": settings}


def build_toolkit_payload(toolkit: dict) -> dict:
    """Build a POST payload for creating a toolkit on the target.

    Maps type, name, description, settings directly from source.
    """
    return {
        "type": toolkit["type"],
        "name": toolkit.get("name", ""),
        "description": toolkit.get("description"),
        "settings": toolkit.get("settings"),
    }


def main() -> int:
    """Parse CLI args, run the copy flow, print summary."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    env_names = ", ".join(ENV_URLS)
    parser = argparse.ArgumentParser(
        description="Copy toolkits from source to target.",
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

    # Step 1: List all toolkits from source
    source_toolkits = source.list_toolkits()
    log.info("Source toolkits: %d", len(source_toolkits))

    # Step 2: List all toolkits from target
    target_toolkits = target.list_toolkits()
    log.info("Target toolkits: %d", len(target_toolkits))

    # Step 3: Compare by toolkit_name — find toolkits missing on target
    target_names: set[str] = {t["toolkit_name"] for t in target_toolkits if t.get("toolkit_name")}
    to_copy = [
        t for t in source_toolkits
        if t.get("toolkit_name") and t["toolkit_name"] not in target_names
    ]

    log.info("Toolkits to copy: %d (missing on target)", len(to_copy))
    for t in to_copy:
        log.info("  - %s (type=%s, name=%s)", t["toolkit_name"], t["type"], t.get("name", ""))

    if not to_copy:
        log.info("Nothing to copy.")
        return 0

    # Step 4: Create missing toolkits on target
    errors: list[str] = []
    copied = 0
    # Collect tool names not allowed anymore, by toolkit type (for yellow summary)
    invalid_by_type: dict[str, set[str]] = {}

    for toolkit in to_copy:
        toolkit_name = toolkit["toolkit_name"]
        toolkit_payload = build_toolkit_payload(toolkit)

        log.info("  Creating: %s (type=%s) ...", toolkit_name, toolkit["type"])
        result = target.create_tool(toolkit_payload)
        if result.get("success"):
            new_id = result["data"].get("id")
            log.info("    -> target id=%s", new_id)
            copied += 1
        else:
            err = result.get("error", "")
            invalid, allowed = _selected_tools_diff(toolkit_payload, err)
            sent = (toolkit_payload.get("settings") or {}).get("selected_tools") or []

            if invalid and allowed:
                tk_type = toolkit.get("type") or "unknown"
                invalid_by_type.setdefault(tk_type, set()).update(invalid)
                log.warning("  %s: first attempt failed — invalid selected_tools (not in target allowlist): %s", toolkit_name, invalid)
                retry_payload = _payload_with_allowed_tools_only(toolkit_payload, allowed)
                log.info("  Retrying: %s with allowed selected_tools only ...", toolkit_name)
                result = target.create_tool(retry_payload)
                if result.get("success"):
                    new_id = result["data"].get("id")
                    log.info("    -> target id=%s (created with subset of selected_tools)", new_id)
                    copied += 1
                else:
                    retry_err = result.get("error", "")
                    errors.append(f"{toolkit_name}: {retry_err} (after retry without invalid selected_tools)")
                    log.warning("  %s: retry failed: %s", toolkit_name, retry_err)
            else:
                if invalid:
                    tk_type = toolkit.get("type") or "unknown"
                    invalid_by_type.setdefault(tk_type, set()).update(invalid)
                diff_msg = f" invalid selected_tools (not in target allowlist): {invalid}" if invalid else ""
                if allowed and not invalid:
                    diff_msg = f" target allowlist has {len(allowed)} tools"
                errors.append(f"{toolkit_name}: {err}{diff_msg}")
                log.warning("  %s: %s", toolkit_name, err)
                if invalid:
                    log.warning("    -> diff: sent %d selected_tools; invalid (not allowed on target): %s", len(sent), invalid)

    # Summary
    log.info("\n--- Summary ---")
    log.info("  Toolkits copied: %d / %d", copied, len(to_copy))
    log.info("  Errors: %d", len(errors))
    if invalid_by_type:
        lines = [f"{_YELLOW}Tools not allowed anymore (by toolkit type):{_RESET}"]
        for tk_type in sorted(invalid_by_type):
            tools = sorted(invalid_by_type[tk_type])
            lines.append(f"  {_YELLOW}{tk_type}: {', '.join(tools)}{_RESET}")
        log.info("\n".join(lines))
    if errors:
        for e in errors:
            log.info("    - %s", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
