#!/usr/bin/env python3
"""
Delete all applications in a project (single environment).

Steps:
  1. Fetch all applications from the project
  2. Delete each application one by one via DELETE

Setup (use a virtual environment; the only dependency is "requests"):

    pip install requests

Usage:

    python delete_apps.py --env stage --project-id 52 --token TOKEN

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

    env_names = ", ".join(ENV_URLS)
    parser = argparse.ArgumentParser(
        description="Delete all applications in a project.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--env",        required=True, choices=ENV_URLS, help=f"Environment ({env_names})")
    parser.add_argument("--project-id", required=True, type=int,         help="Project ID")
    parser.add_argument("--token",      required=True,                   help="Bearer token")
    args = parser.parse_args()

    api = AlitaAPI(ENV_URLS[args.env], args.project_id, args.token)

    log.info("Env: %s (%s) project=%d", args.env, api.base_url, api.project_id)

    apps = api.list_apps()
    log.info("Applications: %d", len(apps))

    if not apps:
        log.info("Nothing to delete.")
        return 0

    deleted = 0
    errors: list[str] = []

    for app in apps:
        app_id = app.get("id")
        name = app.get("name") or f"id={app_id}"
        if app_id is None:
            continue
        result = api.delete_app(app_id)
        if result.get("success"):
            deleted += 1
            log.info("  Deleted: %s (id=%s)", name, app_id)
        else:
            err = result.get("error", result)
            errors.append(f"{name}: {err}")
            log.warning("  %s: %s", name, err)

    log.info("\n--- Summary ---")
    log.info("  Deleted: %d / %d", deleted, len(apps))
    log.info("  Errors: %d", len(errors))
    if errors:
        for e in errors:
            log.info("    - %s", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
