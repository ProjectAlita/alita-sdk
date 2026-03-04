#!/usr/bin/env python3
"""
Delete all configurations in a project (single environment), excluding ignored types.

Steps:
  1. List all configurations from the project
  2. Exclude configs whose type is in IGNORED_CONFIG_TYPES
  3. Delete each remaining config one by one via DELETE

Setup (use a virtual environment; the only dependency is "requests"):

    pip install requests

Usage:

    python delete_configs.py --env stage --project-id 52 --token TOKEN

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
    "pgvector",
}


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    env_names = ", ".join(ENV_URLS)
    parser = argparse.ArgumentParser(
        description="Delete all configurations in a project (excluding ignored types).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--env",        required=True, choices=ENV_URLS, help=f"Environment ({env_names})")
    parser.add_argument("--project-id", required=True, type=int,         help="Project ID")
    parser.add_argument("--token",      required=True,                   help="Bearer token")
    args = parser.parse_args()

    api = AlitaAPI(ENV_URLS[args.env], args.project_id, args.token)

    log.info("Env: %s (%s) project=%d", args.env, api.base_url, api.project_id)

    configs = api.list_configs()
    to_delete = [c for c in configs if c.get("type") not in IGNORED_CONFIG_TYPES]
    skipped_count = len(configs) - len(to_delete)

    log.info("Configs: %d total, %d to delete (skip %d ignored types)", len(configs), len(to_delete), skipped_count)

    if not to_delete:
        log.info("Nothing to delete.")
        return 0

    deleted = 0
    errors: list[str] = []

    for config in to_delete:
        config_id = config.get("id")
        title = config.get("alita_title") or config.get("label") or f"id={config_id}"
        if config_id is None:
            continue
        result = api.delete_config(config_id)
        if result.get("success"):
            deleted += 1
            log.info("  Deleted: %s (id=%s, type=%s)", title, config_id, config.get("type", ""))
        else:
            err = result.get("error", result)
            errors.append(f"{title}: {err}")
            log.warning("  %s: %s", title, err)

    log.info("\n--- Summary ---")
    log.info("  Deleted: %d / %d", deleted, len(to_delete))
    log.info("  Skipped (ignored types): %d", skipped_count)
    log.info("  Errors: %d", len(errors))
    if errors:
        for e in errors:
            log.info("    - %s", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
