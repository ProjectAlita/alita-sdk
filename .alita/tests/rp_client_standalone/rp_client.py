#!/usr/bin/env python3
"""
Standalone ReportPortal Client for Bash-based Tests

This client provides a simple interface to report test results to ReportPortal
without requiring pytest or any other test framework.

Usage as Python library:
    from rp_client import ReportPortalClient

    with ReportPortalClient() as rp:
        rp.start_launch("My Test Run", description="Running bash tests")

        suite_id = rp.start_suite("Integration Tests")
        test_id = rp.start_test("test_api_endpoint", parent_id=suite_id)

        rp.log(test_id, "Executing curl command...")
        rp.log(test_id, "Response: 200 OK", level="INFO")

        rp.finish_test(test_id, status="PASSED")
        rp.finish_suite(suite_id)

        rp.finish_launch()

Usage from CLI (for bash scripts):
    # Start a launch and get launch ID
    LAUNCH_ID=$(python rp_client.py start-launch --name "Bash Tests")

    # Start a test
    TEST_ID=$(python rp_client.py start-test --name "test_something" --launch-id $LAUNCH_ID)

    # Log messages
    python rp_client.py log --item-id $TEST_ID --message "Test output here"
    python rp_client.py log --item-id $TEST_ID --message "Error occurred" --level ERROR

    # Attach files
    python rp_client.py log --item-id $TEST_ID --message "Screenshot" --attachment screenshot.png

    # Finish test with status
    python rp_client.py finish-test --item-id $TEST_ID --status PASSED

    # Finish launch
    python rp_client.py finish-launch --launch-id $LAUNCH_ID
"""

import argparse
import json
import mimetypes
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import requests

# Try to load dotenv if available
try:
    from dotenv import load_dotenv
    # Load .env from current directory or parent directories
    load_dotenv()
    # Also try .env.local if it exists
    env_local = Path(__file__).parent / ".env.local"
    if env_local.exists():
        load_dotenv(env_local)
except ImportError:
    pass  # dotenv not installed, use environment variables directly


@dataclass
class RPConfig:
    """ReportPortal configuration."""
    endpoint: str = field(default_factory=lambda: os.getenv(
        "RP_ENDPOINT", ""
    ))
    project: str = field(default_factory=lambda: os.getenv(
        "RP_PROJECT", ""
    ))
    api_key: str = field(default_factory=lambda: os.getenv(
        "RP_API_KEY", ""
    ))
    launch_name: str = field(default_factory=lambda: os.getenv(
        "RP_LAUNCH", "Test Automation"
    ))

    def validate(self) -> None:
        """Validate required configuration."""
        missing = []
        if not self.endpoint:
            missing.append("RP_ENDPOINT")
        if not self.project:
            missing.append("RP_PROJECT")
        if not self.api_key:
            missing.append("RP_API_KEY")
        if missing:
            raise ValueError(
                f"Missing required configuration: {', '.join(missing)}. "
                "Set via environment variables or .env file."
            )

    @property
    def base_url(self) -> str:
        """Get the base API URL."""
        return f"{self.endpoint}/api/v2/{self.project}"

    @property
    def headers(self) -> dict:
        """Get authentication headers."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }


class ReportPortalClient:
    """
    Standalone ReportPortal client for reporting test results.

    Can be used as a context manager or standalone.

    Example:
        # As context manager (auto-finishes launch)
        with ReportPortalClient() as rp:
            rp.start_launch("My Tests")
            test_id = rp.start_test("test_something")
            rp.finish_test(test_id, "PASSED")

        # Standalone (manual control)
        rp = ReportPortalClient()
        rp.start_launch("My Tests")
        # ... run tests ...
        rp.finish_launch()
    """

    # Valid test statuses
    STATUSES = {"PASSED", "FAILED", "SKIPPED", "INTERRUPTED", "CANCELLED"}

    # Valid log levels
    LOG_LEVELS = {"TRACE", "DEBUG", "INFO", "WARN", "ERROR", "FATAL"}

    # Item types
    ITEM_TYPES = {
        "SUITE": "SUITE",
        "TEST": "STEP",
        "STEP": "STEP",
        "BEFORE_CLASS": "BEFORE_CLASS",
        "AFTER_CLASS": "AFTER_CLASS",
    }

    def __init__(self, config: Optional[RPConfig] = None):
        """
        Initialize the ReportPortal client.

        Args:
            config: Optional RPConfig instance. If not provided, reads from env.
        """
        self.config = config or RPConfig()
        self.config.validate()

        self.session = requests.Session()
        self.session.headers.update(self.config.headers)

        self._launch_id: Optional[str] = None
        self._launch_uuid: Optional[str] = None
        self._items: dict[str, dict] = {}  # item_id -> item info

    def __enter__(self) -> "ReportPortalClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Auto-finish launch on context exit."""
        if self._launch_uuid:
            # Finish any open items
            for item_id, item in list(self._items.items()):
                if item.get("status") is None:
                    status = "FAILED" if exc_type else "PASSED"
                    self.finish_item(item_id, status)

            self.finish_launch()

        self.session.close()

    def _timestamp(self) -> str:
        """Get current timestamp in milliseconds."""
        return str(int(time.time() * 1000))

    def _request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[dict] = None,
        files: Optional[dict] = None,
    ) -> dict:
        """
        Make an HTTP request to ReportPortal.

        Args:
            method: HTTP method (GET, POST, PUT, PATCH)
            endpoint: API endpoint path
            json_data: JSON body data
            files: Files for multipart upload

        Returns:
            Response JSON data

        Raises:
            requests.HTTPError: If request fails
        """
        url = f"{self.config.base_url}{endpoint}"

        if files:
            # Multipart request for file uploads
            # IMPORTANT: Don't use session for multipart - its Content-Type header breaks it
            # ReportPortal expects format: [(field_name, (filename, content, content_type)), ...]
            # JSON part: ("json_request_part", (None, json_string, "application/json"))
            # File part: ("file", (filename, file_bytes, mime_type))
            headers = {"Authorization": f"Bearer {self.config.api_key}"}
            multipart_files: list[tuple] = []

            # Add JSON request as a file part (None for filename means no filename)
            if json_data:
                json_string = json.dumps([json_data])
                multipart_files.append(
                    ("json_request_part", (None, json_string, "application/json"))
                )

            # Add the actual file(s)
            for key, value in files.items():
                multipart_files.append((key, value))

            # Use requests directly (not session) to avoid Content-Type header conflict
            response = requests.request(method, url, headers=headers, files=multipart_files)
        else:
            kwargs: dict[str, Any] = {}
            if json_data:
                kwargs["json"] = json_data
            response = self.session.request(method, url, **kwargs)

        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            print(f"ReportPortal API error: {e}", file=sys.stderr)
            print(f"Response: {response.text}", file=sys.stderr)
            raise

        if response.text:
            return response.json()
        return {}

    # -------------------------------------------------------------------------
    # Launch Management
    # -------------------------------------------------------------------------

    def start_launch(
        self,
        name: Optional[str] = None,
        description: str = "",
        attributes: Optional[list[dict]] = None,
        mode: str = "DEFAULT",
    ) -> str:
        """
        Start a new launch (test run).

        Args:
            name: Launch name. Defaults to config launch_name.
            description: Launch description.
            attributes: List of attributes [{"key": "k", "value": "v"}, ...]
            mode: Launch mode (DEFAULT or DEBUG)

        Returns:
            Launch UUID
        """
        payload = {
            "name": name or self.config.launch_name,
            "description": description,
            "startTime": self._timestamp(),
            "mode": mode,
            "attributes": attributes or [
                {"key": "framework", "value": "bash"},
                {"key": "type", "value": "automation"},
            ],
        }

        result = self._request("POST", "/launch", json_data=payload)
        self._launch_uuid = result.get("id")
        self._launch_id = self._launch_uuid  # They're the same in v2 API

        print(f"Started launch: {self._launch_uuid}", file=sys.stderr)
        return self._launch_uuid

    def finish_launch(self, status: Optional[str] = None) -> dict:
        """
        Finish the current launch.

        Args:
            status: Optional overall status. If not provided, computed from items.

        Returns:
            API response
        """
        if not self._launch_uuid:
            raise RuntimeError("No launch started. Call start_launch() first.")

        # Compute status from items if not provided
        if status is None:
            statuses = [item.get("status", "PASSED") for item in self._items.values()]
            if "FAILED" in statuses:
                status = "FAILED"
            elif "SKIPPED" in statuses and not any(s == "PASSED" for s in statuses):
                status = "SKIPPED"
            else:
                status = "PASSED"

        payload = {
            "endTime": self._timestamp(),
            "status": status,
        }

        result = self._request("PUT", f"/launch/{self._launch_uuid}/finish", json_data=payload)
        print(f"Finished launch: {self._launch_uuid} ({status})", file=sys.stderr)

        self._launch_uuid = None
        return result

    # -------------------------------------------------------------------------
    # Test Item Management
    # -------------------------------------------------------------------------

    def start_item(
        self,
        name: str,
        item_type: str = "STEP",
        parent_id: Optional[str] = None,
        description: str = "",
        attributes: Optional[list[dict]] = None,
        code_ref: Optional[str] = None,
        parameters: Optional[list[dict]] = None,
    ) -> str:
        """
        Start a test item (suite, test, or step).

        Args:
            name: Item name
            item_type: Type (SUITE, STEP, BEFORE_CLASS, AFTER_CLASS)
            parent_id: Parent item UUID for nesting
            description: Item description
            attributes: List of attributes
            code_ref: Code reference (e.g., "test_file.py::test_name")
            parameters: Test parameters [{"key": "param", "value": "value"}]

        Returns:
            Item UUID
        """
        if not self._launch_uuid:
            raise RuntimeError("No launch started. Call start_launch() first.")

        payload = {
            "name": name,
            "type": self.ITEM_TYPES.get(item_type.upper(), "STEP"),
            "launchUuid": self._launch_uuid,
            "startTime": self._timestamp(),
            "description": description,
            "attributes": attributes or [],
            "hasStats": item_type.upper() != "SUITE",
        }

        if parent_id:
            payload["parentId"] = parent_id

        if code_ref:
            payload["codeRef"] = code_ref

        if parameters:
            payload["parameters"] = parameters

        result = self._request("POST", "/item", json_data=payload)
        item_uuid = result.get("id")

        self._items[item_uuid] = {
            "name": name,
            "type": item_type,
            "parent_id": parent_id,
            "status": None,
        }

        print(f"Started {item_type}: {name} ({item_uuid})", file=sys.stderr)
        return item_uuid

    def start_suite(
        self,
        name: str,
        parent_id: Optional[str] = None,
        description: str = "",
        attributes: Optional[list[dict]] = None,
    ) -> str:
        """
        Start a test suite.

        Args:
            name: Suite name
            parent_id: Parent suite UUID for nesting
            description: Suite description
            attributes: List of attributes

        Returns:
            Suite UUID
        """
        return self.start_item(
            name=name,
            item_type="SUITE",
            parent_id=parent_id,
            description=description,
            attributes=attributes,
        )

    def start_test(
        self,
        name: str,
        parent_id: Optional[str] = None,
        description: str = "",
        attributes: Optional[list[dict]] = None,
        code_ref: Optional[str] = None,
    ) -> str:
        """
        Start a test case.

        Args:
            name: Test name
            parent_id: Parent suite UUID
            description: Test description
            attributes: List of attributes
            code_ref: Code reference

        Returns:
            Test UUID
        """
        return self.start_item(
            name=name,
            item_type="STEP",
            parent_id=parent_id,
            description=description,
            attributes=attributes,
            code_ref=code_ref,
        )

    def finish_item(
        self,
        item_id: str,
        status: str = "PASSED",
        description: Optional[str] = None,
        attributes: Optional[list[dict]] = None,
        issue: Optional[dict] = None,
        failure_message: Optional[str] = None,
        failure_stacktrace: Optional[str] = None,
    ) -> dict:
        """
        Finish a test item.

        Args:
            item_id: Item UUID to finish
            status: Final status (PASSED, FAILED, SKIPPED, INTERRUPTED, CANCELLED)
            description: Optional description update
            attributes: Optional attributes to add
            issue: Optional issue info {"issueType": "...", "comment": "..."}
            failure_message: Optional failure message (for failed tests)
            failure_stacktrace: Optional failure stack trace (for failed tests)

        Returns:
            API response
        """
        if status.upper() not in self.STATUSES:
            raise ValueError(f"Invalid status: {status}. Must be one of {self.STATUSES}")

        payload = {
            "endTime": self._timestamp(),
            "status": status.upper(),
            "launchUuid": self._launch_uuid,
        }

        if description:
            payload["description"] = description

        if attributes:
            payload["attributes"] = attributes

        if issue:
            payload["issue"] = issue

        if failure_message:
            payload["failure_message"] = failure_message

        if failure_stacktrace:
            payload["failure_stacktrace"] = failure_stacktrace

        result = self._request("PUT", f"/item/{item_id}", json_data=payload)

        if item_id in self._items:
            self._items[item_id]["status"] = status.upper()

        item_name = self._items.get(item_id, {}).get("name", item_id)
        print(f"Finished: {item_name} ({status})", file=sys.stderr)

        return result

    def finish_test(self, item_id: str, status: str = "PASSED", **kwargs) -> dict:
        """Alias for finish_item for tests."""
        return self.finish_item(item_id, status, **kwargs)

    def finish_suite(self, item_id: str, status: str = "PASSED", **kwargs) -> dict:
        """Alias for finish_item for suites."""
        return self.finish_item(item_id, status, **kwargs)

    # -------------------------------------------------------------------------
    # Logging
    # -------------------------------------------------------------------------

    def log(
        self,
        item_id: str,
        message: str,
        level: str = "INFO",
        attachment: Optional[dict | str | Path] = None,
    ) -> dict:
        """
        Log a message to a test item.

        Args:
            item_id: Item UUID to log to
            message: Log message
            level: Log level (TRACE, DEBUG, INFO, WARN, ERROR, FATAL)
            attachment: Optional attachment - can be:
                - dict with {"name": str, "data": bytes, "mime": str}
                - str/Path to a file to attach

        Returns:
            API response
        """
        if level.upper() not in self.LOG_LEVELS:
            level = "INFO"

        log_entry = {
            "itemUuid": item_id,
            "launchUuid": self._launch_uuid,
            "time": self._timestamp(),
            "message": message,
            "level": level.upper(),
        }

        # Handle file path attachment
        if attachment and isinstance(attachment, (str, Path)):
            file_path = Path(attachment)
            if file_path.exists():
                mime_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
                attachment = {
                    "name": file_path.name,
                    "data": file_path.read_bytes(),
                    "mime": mime_type,
                }
            else:
                print(f"Warning: Attachment file not found: {file_path}", file=sys.stderr)
                attachment = None

        # Handle attachment upload
        if attachment and isinstance(attachment, dict):
            log_entry["file"] = {"name": attachment["name"]}

            files = {
                "file": (
                    attachment["name"],
                    attachment["data"],
                    attachment.get("mime", "application/octet-stream"),
                ),
            }

            return self._request("POST", "/log", json_data=log_entry, files=files)

        # Simple log without attachment
        return self._request("POST", "/log", json_data=log_entry)

    def log_error(self, item_id: str, message: str, **kwargs) -> dict:
        """Log an error message."""
        return self.log(item_id, message, level="ERROR", **kwargs)

    def log_warning(self, item_id: str, message: str, **kwargs) -> dict:
        """Log a warning message."""
        return self.log(item_id, message, level="WARN", **kwargs)

    def log_debug(self, item_id: str, message: str, **kwargs) -> dict:
        """Log a debug message."""
        return self.log(item_id, message, level="DEBUG", **kwargs)

    def attach_file(self, item_id: str, file_path: str | Path, message: str = "") -> dict:
        """
        Attach a file to a test item.

        Args:
            item_id: Item UUID
            file_path: Path to file to attach
            message: Optional message to accompany the attachment

        Returns:
            API response
        """
        return self.log(item_id, message or f"Attachment: {Path(file_path).name}", attachment=file_path)


# =============================================================================
# CLI Interface
# =============================================================================

def cli_start_launch(args: argparse.Namespace) -> None:
    """Start a new launch and print its UUID."""
    config = RPConfig()
    if args.endpoint:
        config.endpoint = args.endpoint
    if args.project:
        config.project = args.project
    if args.api_key:
        config.api_key = args.api_key

    client = ReportPortalClient(config)

    attributes = []
    if args.attributes:
        for attr in args.attributes:
            if ":" in attr:
                key, value = attr.split(":", 1)
                attributes.append({"key": key, "value": value})

    launch_uuid = client.start_launch(
        name=args.name,
        description=args.description or "",
        attributes=attributes or None,
    )

    # Print only the UUID for capture in bash
    print(launch_uuid)


def cli_finish_launch(args: argparse.Namespace) -> None:
    """Finish an existing launch."""
    config = RPConfig()
    if args.endpoint:
        config.endpoint = args.endpoint
    if args.project:
        config.project = args.project
    if args.api_key:
        config.api_key = args.api_key

    client = ReportPortalClient(config)
    client._launch_uuid = args.launch_id
    client._launch_id = args.launch_id

    client.finish_launch(status=args.status)


def cli_start_item(args: argparse.Namespace) -> None:
    """Start a test item and print its UUID."""
    config = RPConfig()
    if args.endpoint:
        config.endpoint = args.endpoint
    if args.project:
        config.project = args.project
    if args.api_key:
        config.api_key = args.api_key

    client = ReportPortalClient(config)
    client._launch_uuid = args.launch_id
    client._launch_id = args.launch_id

    attributes = []
    if args.attributes:
        for attr in args.attributes:
            if ":" in attr:
                key, value = attr.split(":", 1)
                attributes.append({"key": key, "value": value})

    item_uuid = client.start_item(
        name=args.name,
        item_type=args.type,
        parent_id=args.parent_id,
        description=args.description or "",
        attributes=attributes or None,
        code_ref=args.code_ref,
    )

    print(item_uuid)


def cli_finish_item(args: argparse.Namespace) -> None:
    """Finish a test item."""
    config = RPConfig()
    if args.endpoint:
        config.endpoint = args.endpoint
    if args.project:
        config.project = args.project
    if args.api_key:
        config.api_key = args.api_key

    client = ReportPortalClient(config)
    client._launch_uuid = args.launch_id
    client._launch_id = args.launch_id

    client.finish_item(args.item_id, status=args.status)


def cli_log(args: argparse.Namespace) -> None:
    """Log a message to a test item."""
    config = RPConfig()
    if args.endpoint:
        config.endpoint = args.endpoint
    if args.project:
        config.project = args.project
    if args.api_key:
        config.api_key = args.api_key

    client = ReportPortalClient(config)
    client._launch_uuid = args.launch_id
    client._launch_id = args.launch_id

    client.log(
        item_id=args.item_id,
        message=args.message,
        level=args.level,
        attachment=args.attachment,
    )


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="ReportPortal CLI client for bash-based test automation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start a launch
  LAUNCH=$(python rp_client.py start-launch --name "My Tests")

  # Start a test suite
  SUITE=$(python rp_client.py start-item --launch-id $LAUNCH --name "API Tests" --type SUITE)

  # Start a test
  TEST=$(python rp_client.py start-item --launch-id $LAUNCH --name "test_endpoint" --parent-id $SUITE)

  # Log messages
  python rp_client.py log --launch-id $LAUNCH --item-id $TEST --message "Running test..."
  python rp_client.py log --launch-id $LAUNCH --item-id $TEST --message "Error!" --level ERROR

  # Attach a file
  python rp_client.py log --launch-id $LAUNCH --item-id $TEST --message "Screenshot" --attachment ./screenshot.png

  # Finish test and suite
  python rp_client.py finish-item --launch-id $LAUNCH --item-id $TEST --status PASSED
  python rp_client.py finish-item --launch-id $LAUNCH --item-id $SUITE --status PASSED

  # Finish launch
  python rp_client.py finish-launch --launch-id $LAUNCH

Environment Variables:
  RP_ENDPOINT   ReportPortal API endpoint (e.g., https://reportportal.example.com/api/receiver)
  RP_PROJECT    ReportPortal project UUID
  RP_API_KEY    ReportPortal API key
  RP_LAUNCH     Default launch name (optional)
""",
    )

    # Global options
    parser.add_argument("--endpoint", help="ReportPortal endpoint URL")
    parser.add_argument("--project", help="ReportPortal project ID")
    parser.add_argument("--api-key", help="ReportPortal API key")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # start-launch
    p_start_launch = subparsers.add_parser("start-launch", help="Start a new launch")
    p_start_launch.add_argument("--name", required=True, help="Launch name")
    p_start_launch.add_argument("--description", help="Launch description")
    p_start_launch.add_argument(
        "--attributes", nargs="*",
        help="Attributes in key:value format (e.g., env:staging type:smoke)"
    )
    p_start_launch.set_defaults(func=cli_start_launch)

    # finish-launch
    p_finish_launch = subparsers.add_parser("finish-launch", help="Finish a launch")
    p_finish_launch.add_argument("--launch-id", required=True, help="Launch UUID")
    p_finish_launch.add_argument(
        "--status",
        choices=["PASSED", "FAILED", "SKIPPED", "INTERRUPTED", "CANCELLED"],
        help="Final launch status (auto-computed if not provided)"
    )
    p_finish_launch.set_defaults(func=cli_finish_launch)

    # start-item (generic)
    p_start_item = subparsers.add_parser("start-item", help="Start a test item")
    p_start_item.add_argument("--launch-id", required=True, help="Launch UUID")
    p_start_item.add_argument("--name", required=True, help="Item name")
    p_start_item.add_argument(
        "--type", default="STEP",
        choices=["SUITE", "STEP", "BEFORE_CLASS", "AFTER_CLASS"],
        help="Item type (default: STEP)"
    )
    p_start_item.add_argument("--parent-id", help="Parent item UUID")
    p_start_item.add_argument("--description", help="Item description")
    p_start_item.add_argument("--code-ref", help="Code reference")
    p_start_item.add_argument(
        "--attributes", nargs="*",
        help="Attributes in key:value format"
    )
    p_start_item.set_defaults(func=cli_start_item)

    # start-suite (convenience alias)
    p_start_suite = subparsers.add_parser("start-suite", help="Start a test suite")
    p_start_suite.add_argument("--launch-id", required=True, help="Launch UUID")
    p_start_suite.add_argument("--name", required=True, help="Suite name")
    p_start_suite.add_argument("--parent-id", help="Parent suite UUID")
    p_start_suite.add_argument("--description", help="Suite description")
    p_start_suite.add_argument("--attributes", nargs="*", help="Attributes in key:value format")
    p_start_suite.set_defaults(func=lambda args: cli_start_item(
        argparse.Namespace(**vars(args), type="SUITE", code_ref=None)
    ))

    # start-test (convenience alias)
    p_start_test = subparsers.add_parser("start-test", help="Start a test")
    p_start_test.add_argument("--launch-id", required=True, help="Launch UUID")
    p_start_test.add_argument("--name", required=True, help="Test name")
    p_start_test.add_argument("--parent-id", help="Parent suite UUID")
    p_start_test.add_argument("--description", help="Test description")
    p_start_test.add_argument("--code-ref", help="Code reference")
    p_start_test.add_argument("--attributes", nargs="*", help="Attributes in key:value format")
    p_start_test.set_defaults(func=lambda args: cli_start_item(
        argparse.Namespace(**vars(args), type="STEP")
    ))

    # finish-item
    p_finish_item = subparsers.add_parser("finish-item", help="Finish a test item")
    p_finish_item.add_argument("--launch-id", required=True, help="Launch UUID")
    p_finish_item.add_argument("--item-id", required=True, help="Item UUID")
    p_finish_item.add_argument(
        "--status", default="PASSED",
        choices=["PASSED", "FAILED", "SKIPPED", "INTERRUPTED", "CANCELLED"],
        help="Item status (default: PASSED)"
    )
    p_finish_item.set_defaults(func=cli_finish_item)

    # finish-test (convenience alias)
    p_finish_test = subparsers.add_parser("finish-test", help="Finish a test")
    p_finish_test.add_argument("--launch-id", required=True, help="Launch UUID")
    p_finish_test.add_argument("--item-id", required=True, help="Test UUID")
    p_finish_test.add_argument(
        "--status", default="PASSED",
        choices=["PASSED", "FAILED", "SKIPPED", "INTERRUPTED", "CANCELLED"],
        help="Test status (default: PASSED)"
    )
    p_finish_test.set_defaults(func=cli_finish_item)

    # finish-suite (convenience alias)
    p_finish_suite = subparsers.add_parser("finish-suite", help="Finish a suite")
    p_finish_suite.add_argument("--launch-id", required=True, help="Launch UUID")
    p_finish_suite.add_argument("--item-id", required=True, help="Suite UUID")
    p_finish_suite.add_argument(
        "--status", default="PASSED",
        choices=["PASSED", "FAILED", "SKIPPED", "INTERRUPTED", "CANCELLED"],
        help="Suite status (default: PASSED)"
    )
    p_finish_suite.set_defaults(func=cli_finish_item)

    # log
    p_log = subparsers.add_parser("log", help="Log a message")
    p_log.add_argument("--launch-id", required=True, help="Launch UUID")
    p_log.add_argument("--item-id", required=True, help="Item UUID")
    p_log.add_argument("--message", required=True, help="Log message")
    p_log.add_argument(
        "--level", default="INFO",
        choices=["TRACE", "DEBUG", "INFO", "WARN", "ERROR", "FATAL"],
        help="Log level (default: INFO)"
    )
    p_log.add_argument("--attachment", help="File path to attach")
    p_log.set_defaults(func=cli_log)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
