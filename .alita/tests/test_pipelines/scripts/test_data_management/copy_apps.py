#!/usr/bin/env python3
"""
Copy applications from source Alita environment to target.

Steps:
  1. Fetch all applications from the source project
  2. Fetch all applications from the target project
  3. Compare by name — identify apps that exist on source but not target
  4. For each missing app, fetch full details and create on target

Setup (use a virtual environment; the only dependency is "requests"):

    pip install requests

Usage:

    python copy_apps.py \\
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


def _clean_tags(source_tags: list) -> list[dict]:
    """Keep only name + color from source tags."""
    return [
        {
            "name": tag["name"],
            "data": {"color": (tag.get("data") or {}).get("color", "red")},
        }
        for tag in source_tags
        if isinstance(tag, dict) and tag.get("name")
    ]


SAFE_LLM_KEYS: set[str] = {
    "model_name",
    "temperature",
    "max_tokens",
    "top_p",
    "top_k",
    "stream",
}


def _clean_llm_settings(llm: dict) -> dict:
    """Keep only known safe keys from llm_settings."""
    return {k: v for k, v in llm.items() if k in SAFE_LLM_KEYS}


def build_app_payload(app_details: dict) -> dict | None:
    """Build a POST payload for creating an application on the target.

    Tools are empty — they reference source-specific IDs and must be
    linked separately after creation.
    llm_settings are filtered to safe keys only.
    """
    ver = app_details.get("version_details")
    if not ver:
        return None

    return {
        "name": app_details.get("name") or "Unnamed",
        "description": app_details.get("description") or "",
        "versions": [
            {
                "name": ver.get("name", "base"),
                "tags": _clean_tags(ver.get("tags") or []),
                "instructions": ver.get("instructions") or "",
                "llm_settings": _clean_llm_settings(ver.get("llm_settings") or {}),
                "variables": ver.get("variables") or [],
                "tools": [],
                "conversation_starters": ver.get("conversation_starters") or [],
                "agent_type": ver["agent_type"],
                "welcome_message": ver.get("welcome_message") or "",
                "meta": ver.get("meta") or {"step_limit": 100},
            }
        ],
    }


def main() -> int:
    """Parse CLI args, run the copy flow, print summary."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    env_names = ", ".join(ENV_URLS)
    parser = argparse.ArgumentParser(
        description="Copy applications from source to target.",
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

    # Step 1: Fetch all applications from source
    source_apps = source.list_apps()
    log.info("Source apps: %d", len(source_apps))

    # Step 2: Fetch all applications from target
    target_apps = target.list_apps()
    log.info("Target apps: %d", len(target_apps))

    # Step 3: Compare by name — find apps missing on target
    target_names: set[str] = {a["name"] for a in target_apps if a.get("name")}
    to_copy = [a for a in source_apps if a.get("name") and a["name"] not in target_names]

    log.info("Apps to copy: %d (missing on target)", len(to_copy))
    for a in to_copy:
        log.info("  - %s (id=%d)", a["name"], a["id"])

    if not to_copy:
        log.info("Nothing to copy.")
        return 0

    # Step 4: Create missing apps on target
    errors: list[str] = []
    copied = 0

    for app in to_copy:
        app_id = app["id"]
        name = app["name"]

        log.info("  Copying: %s (source id=%d) ...", name, app_id)

        app_details = source.get_app_details(app_id)
        if not app_details:
            errors.append(f"{name}: failed to get details from source")
            log.warning("  %s: failed to get details from source", name)
            continue

        app_payload = build_app_payload(app_details)
        if not app_payload:
            errors.append(f"{name}: could not build payload (no version data?)")
            log.warning("  %s: could not build payload (no version data?)", name)
            continue

        result = target.create_app(app_payload)
        if not result.get("success"):
            err = result.get("error", result)
            errors.append(f"{name}: {err}")
            log.warning("  %s: %s", name, err)
            continue

        log.info("    -> target id=%s", result["data"].get("id"))
        copied += 1

    # Summary
    log.info("\n--- Summary ---")
    log.info("  Apps copied: %d / %d", copied, len(to_copy))
    log.info("  Errors: %d", len(errors))
    if errors:
        for e in errors:
            log.info("    - %s", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
