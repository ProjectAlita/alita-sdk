#!/usr/bin/env python3
"""
Copy configurations from source Alita environment to target.

Steps:
  1. List all configurations from the source project
  2. List all configurations from the target project
  3. Compare by alita_title — identify configs that exist on source but not target
  4. Create the missing configurations on the target

Setup (use a virtual environment; the only dependency is "requests"):

    pip install requests

Usage:

    python copy_configs.py \\
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

IGNORED_CONFIG_TYPES: set[str] = {
    "llm_model",
    "s3_api_credentials",
    "pgvector"
}


def build_config_payload(config: dict) -> dict:
    """Build a POST payload for creating a configuration on the target.

    Only the fields required by the create endpoint are included:
    alita_title, label, type, shared, data.
    """
    return {
        "alita_title": config["alita_title"],
        "label": config.get("label", ""),
        "type": config["type"],
        "shared": config.get("shared", False),
        "data": config.get("data") or {},
    }


def main() -> int:
    """Parse CLI args, run the copy flow, print summary."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    env_names = ", ".join(ENV_URLS)
    parser = argparse.ArgumentParser(
        description="Copy configurations from source to target.",
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

    # Step 1: List all configs from source
    source_configs = source.list_configs()
    log.info("Source configs: %d", len(source_configs))

    # Step 2: List all configs from target
    target_configs = target.list_configs()
    log.info("Target configs: %d", len(target_configs))

    # Step 3: Compare by alita_title — find configs missing on target
    # Skip types listed in IGNORED_CONFIG_TYPES (managed separately per environment)
    target_titles: set[str] = {c["alita_title"] for c in target_configs}
    to_copy = [
        c for c in source_configs
        if c["alita_title"] not in target_titles and c.get("type") not in IGNORED_CONFIG_TYPES
    ]

    log.info("Configs to copy: %d (missing on target)", len(to_copy))
    for c in to_copy:
        log.info("  - %s (type=%s, label=%s)", c["alita_title"], c["type"], c.get("label", ""))

    if not to_copy:
        log.info("Nothing to copy.")
        return 0

    # Step 4: Create missing configs on target
    errors: list[str] = []
    copied = 0

    for config in to_copy:
        title = config["alita_title"]
        config_payload = build_config_payload(config)

        log.info("  Creating: %s (type=%s) ...", title, config["type"])
        result = target.create_config(config_payload)
        if result.get("success"):
            new_id = result["data"].get("id")
            log.info("    -> target id=%s", new_id)
            copied += 1
        else:
            err = result.get("error", "")
            errors.append(f"{title}: {err}")
            log.warning("  %s: %s", title, err)

    # Summary
    log.info("\n--- Summary ---")
    log.info("  Configs copied: %d / %d", copied, len(to_copy))
    log.info("  Errors: %d", len(errors))
    if errors:
        for e in errors:
            log.info("    - %s", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
