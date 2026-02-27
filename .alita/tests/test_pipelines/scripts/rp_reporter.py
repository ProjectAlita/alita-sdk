#!/usr/bin/env python3
"""
ReportPortal Reporter for Alita SDK Test Framework

Integrates the standalone ReportPortal client with the test pipeline framework
to report test results to ReportPortal TMS.

Usage:
    from rp_reporter import ReportPortalReporter

    # In run_suite.py
    reporter = ReportPortalReporter.from_env()
    if reporter:
        with reporter.launch("GitHub Toolkit Tests") as launch_ctx:
            suite_id = reporter.start_suite("Integration Tests")
            
            for test in tests:
                test_id = reporter.start_test(test['name'], parent_id=suite_id)
                result = execute_test(test)
                reporter.log_result(test_id, result)
                reporter.finish_test(test_id, result)
            
            reporter.finish_suite(suite_id)
"""

import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

# Add rp_client_standalone to path if not already available
_RP_CLIENT_DIR = Path(__file__).parent.parent.parent / "rp_client_standalone"
if _RP_CLIENT_DIR.exists() and str(_RP_CLIENT_DIR) not in sys.path:
    sys.path.insert(0, str(_RP_CLIENT_DIR))

try:
    from rp_client import ReportPortalClient, RPConfig
    RP_AVAILABLE = True
except ImportError as e:
    RP_AVAILABLE = False
    _RP_IMPORT_ERROR = str(e)


@dataclass
class ReportPortalConfig:
    """Configuration for ReportPortal integration."""
    enabled: bool = False
    endpoint: Optional[str] = None
    project: Optional[str] = None
    api_key: Optional[str] = None
    launch_name: Optional[str] = None
    launch_description: Optional[str] = None
    launch_attributes: Optional[List[Dict[str, str]]] = None
    mode: str = "DEFAULT"  # DEFAULT or DEBUG
    
    @classmethod
    def from_env(cls, env_prefix: str = "RP_") -> "ReportPortalConfig":
        """
        Load configuration from environment variables.
        
        Environment variables:
            RP_ENABLED - Enable/disable ReportPortal (default: false)
            RP_ENDPOINT - ReportPortal endpoint URL
            RP_PROJECT - Project UUID/name
            RP_API_KEY - API key/token
            RP_LAUNCH - Launch name (optional)
            RP_MODE - Launch mode: DEFAULT or DEBUG (default: DEFAULT)
        """
        enabled = os.getenv(f"{env_prefix}ENABLED", "false").lower() in ("true", "1", "yes", "on")
        
        return cls(
            enabled=enabled,
            endpoint=os.getenv(f"{env_prefix}ENDPOINT"),
            project=os.getenv(f"{env_prefix}PROJECT"),
            api_key=os.getenv(f"{env_prefix}API_KEY"),
            launch_name=os.getenv(f"{env_prefix}LAUNCH"),
            mode=os.getenv(f"{env_prefix}MODE", "DEFAULT").upper(),
        )
    
    def validate(self) -> tuple[bool, Optional[str]]:
        """Validate configuration. Returns (is_valid, error_message)."""
        if not self.enabled:
            return True, None
        
        missing = []
        if not self.endpoint:
            missing.append("RP_ENDPOINT")
        if not self.project:
            missing.append("RP_PROJECT")
        if not self.api_key:
            missing.append("RP_API_KEY")
        
        if missing:
            return False, f"Missing required ReportPortal configuration: {', '.join(missing)}"
        
        return True, None


class ReportPortalReporter:
    """
    Reporter that integrates with the test framework to send results to ReportPortal.
    
    This class wraps the standalone ReportPortalClient and adapts it to work with
    the test framework's data structures (PipelineResult, SuiteResult).
    """
    
    def __init__(self, config: ReportPortalConfig, logger=None):
        """
        Initialize the reporter.
        
        Args:
            config: ReportPortal configuration
            logger: Optional logger instance for debugging
        """
        self.config = config
        self.logger = logger
        self.client: Optional[ReportPortalClient] = None
        self._active = False
        self._suite_ids: Dict[str, str] = {}  # suite_name -> item_id
        self._test_ids: Dict[str, str] = {}  # test_name -> item_id
        
        if not RP_AVAILABLE:
            if logger:
                logger.warning(f"ReportPortal client not available: {_RP_IMPORT_ERROR}")
            return
        
        # Validate config
        is_valid, error = config.validate()
        if not is_valid:
            if logger:
                logger.error(f"ReportPortal configuration invalid: {error}")
            return
        
        if config.enabled:
            try:
                # Initialize the ReportPortal client
                rp_config = RPConfig(
                    endpoint=config.endpoint,
                    project=config.project,
                    api_key=config.api_key,
                    launch_name=config.launch_name or "Alita SDK Tests"
                )
                self.client = ReportPortalClient(rp_config)
                self._active = True
                
                if logger:
                    logger.info("ReportPortal reporter initialized")
            except Exception as e:
                if logger:
                    logger.error(f"Failed to initialize ReportPortal client: {e}")
    
    @classmethod
    def from_env(cls, logger=None) -> Optional["ReportPortalReporter"]:
        """
        Create reporter from environment variables.
        
        Returns None if ReportPortal is not enabled or not available.
        """
        config = ReportPortalConfig.from_env()
        
        if not config.enabled:
            if logger:
                logger.debug("ReportPortal reporting is disabled")
            return None
        
        return cls(config, logger)
    
    @property
    def active(self) -> bool:
        """Check if reporter is active and ready to report."""
        return self._active and self.client is not None
    
    @contextmanager
    def launch(self, name: Optional[str] = None, description: str = "", 
               attributes: Optional[List[Dict[str, str]]] = None):
        """
        Context manager for a test launch.
        
        Usage:
            with reporter.launch("My Tests") as launch_id:
                # Run tests
                pass
        """
        if not self.active:
            yield None
            return
        
        try:
            # Start the launch
            launch_name = name or self.config.launch_name or "Alita SDK Tests"
            attrs = attributes or self.config.launch_attributes or [
                {"key": "framework", "value": "alita-sdk"},
                {"key": "type", "value": "automation"},
            ]
            
            launch_id = self.client.start_launch(
                name=launch_name,
                description=description,
                attributes=attrs,
                mode=self.config.mode
            )
            
            if self.logger:
                self.logger.info(f"Started ReportPortal launch: {launch_name} ({launch_id})")
            
            yield launch_id
            
        finally:
            # Finish the launch
            if self.active and self.client:
                try:
                    self.client.finish_launch()
                    if self.logger:
                        self.logger.info("Finished ReportPortal launch")
                except Exception as e:
                    if self.logger:
                        self.logger.error(f"Error finishing launch: {e}")
    
    def start_suite(self, name: str, description: str = "", 
                   parent_id: Optional[str] = None) -> Optional[str]:
        """
        Start a test suite.
        
        Args:
            name: Suite name
            description: Suite description
            parent_id: Optional parent item ID for nesting
            
        Returns:
            Suite item ID or None if not active
        """
        if not self.active:
            return None
        
        try:
            suite_id = self.client.start_item(
                name=name,
                item_type="SUITE",
                description=description,
                parent_id=parent_id
            )
            self._suite_ids[name] = suite_id
            
            if self.logger:
                self.logger.debug(f"Started suite: {name} ({suite_id})")
            
            return suite_id
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error starting suite {name}: {e}")
            return None
    
    def finish_suite(self, suite_id: Optional[str], status: str = "PASSED") -> bool:
        """
        Finish a test suite.
        
        Args:
            suite_id: Suite item ID (from start_suite)
            status: Suite status (PASSED/FAILED)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.active or not suite_id:
            return False
        
        try:
            self.client.finish_item(suite_id, status=status)
            
            if self.logger:
                self.logger.debug(f"Finished suite: {suite_id} ({status})")
            
            return True
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error finishing suite {suite_id}: {e}")
            return False
    
    def start_test(self, name: str, description: str = "", 
                   parent_id: Optional[str] = None) -> Optional[str]:
        """
        Start a test (pipeline execution).
        
        Args:
            name: Test name
            description: Test description
            parent_id: Optional parent suite ID
            
        Returns:
            Test item ID or None if not active
        """
        if not self.active:
            return None
        
        try:
            test_id = self.client.start_item(
                name=name,
                item_type="STEP",
                description=description,
                parent_id=parent_id
            )
            self._test_ids[name] = test_id
            
            if self.logger:
                self.logger.debug(f"Started test: {name} ({test_id})")
            
            return test_id
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error starting test {name}: {e}")
            return None
    
    def finish_test(self, test_id: Optional[str], result: Dict[str, Any]) -> bool:
        """
        Finish a test with result.
        
        Args:
            test_id: Test item ID (from start_test)
            result: Test result dictionary (from PipelineResult or dict)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.active or not test_id:
            return False
        
        try:
            # Map test result to RP status
            status = self._map_status(result)
            
            # Extract failure information for failed tests
            failure_message = None
            failure_stacktrace = None
            
            error = result.get("error")
            if error and status == "FAILED":
                # Extract failure message (first line or summary)
                error_lines = str(error).strip().split('\n')
                failure_message = error_lines[0] if error_lines else str(error)
                
                # Check if we have a full stack trace
                if len(error_lines) > 1 or 'Traceback' in str(error):
                    failure_stacktrace = str(error)
            
            # Finish the test with failure information
            self.client.finish_item(
                test_id, 
                status=status,
                failure_message=failure_message,
                failure_stacktrace=failure_stacktrace
            )
            
            if self.logger:
                self.logger.debug(f"Finished test: {test_id} ({status})")
            
            return True
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error finishing test {test_id}: {e}")
            return False
    
    def log(self, item_id: Optional[str], message: str, level: str = "INFO",
            attachment: Optional[str] = None) -> bool:
        """
        Log a message to a test item.
        
        Args:
            item_id: Test/suite item ID
            message: Log message
            level: Log level (TRACE/DEBUG/INFO/WARN/ERROR/FATAL)
            attachment: Optional file path to attach
            
        Returns:
            True if successful, False otherwise
        """
        if not self.active or not item_id:
            return False
        
        try:
            self.client.log(item_id, message, level=level, attachment=attachment)
            return True
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error logging to {item_id}: {e}")
            return False
    
    def log_markdown(self, item_id: Optional[str], message: str, level: str = "INFO") -> bool:
        """
        Log a Markdown-formatted message to a test item.
        
        Args:
            item_id: Test/suite item ID
            message: Markdown-formatted message
            level: Log level
            
        Returns:
            True if successful, False otherwise
        """
        if not self.active or not item_id:
            return False
        
        try:
            self.client.log_markdown(item_id, message, level=level)
            return True
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error logging markdown to {item_id}: {e}")
            return False
    
    def log_json(self, item_id: Optional[str], data: Any, title: str = "", 
                 level: str = "INFO", indent: int = 2) -> bool:
        """
        Log JSON data with syntax highlighting to a test item.
        
        Args:
            item_id: Test/suite item ID
            data: Any JSON-serializable data
            title: Optional title above the JSON
            level: Log level
            indent: JSON indentation level
            
        Returns:
            True if successful, False otherwise
        """
        if not self.active or not item_id:
            return False
        
        try:
            self.client.log_json(item_id, data, title=title, level=level, indent=indent)
            return True
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error logging JSON to {item_id}: {e}")
            return False
    
    def log_code(self, item_id: Optional[str], code: str, language: str = "", 
                 title: str = "", level: str = "INFO") -> bool:
        """
        Log code with syntax highlighting to a test item.
        
        Args:
            item_id: Test/suite item ID
            code: Code to log
            language: Programming language for syntax highlighting
            title: Optional title above the code block
            level: Log level
            
        Returns:
            True if successful, False otherwise
        """
        if not self.active or not item_id:
            return False
        
        try:
            self.client.log_code(item_id, code, language=language, title=title, level=level)
            return True
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error logging code to {item_id}: {e}")
            return False
    
    def log_failure(self, item_id: Optional[str], error_message: str, 
                    traceback: str = "", expected: Any = None, actual: Any = None,
                    details: Optional[Dict] = None) -> bool:
        """
        Log a detailed failure report with structured formatting.
        
        Args:
            item_id: Test/suite item ID
            error_message: Main error message
            traceback: Optional traceback string
            expected: Optional expected value
            actual: Optional actual value
            details: Optional dict with additional failure details
            
        Returns:
            True if successful, False otherwise
        """
        if not self.active or not item_id:
            return False
        
        try:
            self.client.log_failure(
                item_id, 
                error_message, 
                traceback=traceback,
                expected=expected, 
                actual=actual,
                details=details
            )
            return True
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error logging failure to {item_id}: {e}")
            return False
    
    def log_error(self, item_id: Optional[str], message: str) -> bool:
        """Log an error message to a test item."""
        if not self.active or not item_id:
            return False
        
        try:
            self.client.log_error(item_id, message)
            return True
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error logging error to {item_id}: {e}")
            return False
    
    def log_warning(self, item_id: Optional[str], message: str) -> bool:
        """Log a warning message to a test item."""
        if not self.active or not item_id:
            return False
        
        try:
            self.client.log_warning(item_id, message)
            return True
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error logging warning to {item_id}: {e}")
            return False
    
    def log_debug(self, item_id: Optional[str], message: str) -> bool:
        """Log a debug message to a test item."""
        if not self.active or not item_id:
            return False
        
        try:
            self.client.log_debug(item_id, message)
            return True
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error logging debug to {item_id}: {e}")
            return False
    
    def attach_file(self, item_id: Optional[str], file_path: str, message: str = "") -> bool:
        """
        Attach a file to a test item.
        
        Args:
            item_id: Test/suite item ID
            file_path: Path to file to attach
            message: Optional message to accompany the attachment
            
        Returns:
            True if successful, False otherwise
        """
        if not self.active or not item_id:
            return False
        
        try:
            self.client.attach_file(item_id, file_path, message=message)
            return True
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error attaching file to {item_id}: {e}")
            return False
    
    def log_result(self, test_id: Optional[str], result: Dict[str, Any]) -> bool:
        """
        Log test result details.
        
        Args:
            test_id: Test item ID
            result: Test result dictionary
            
        Returns:
            True if successful, False otherwise
        """
        if not self.active or not test_id:
            return False
        
        try:
            # Log execution time
            exec_time = result.get("execution_time", 0)
            self.log(test_id, f"⏱️ Execution time: {exec_time:.2f}s", level="INFO")
            
            # Log output as JSON if it's a dict/list, otherwise as text
            output = result.get("output")
            if output:
                if isinstance(output, (dict, list)):
                    # Use structured JSON logging for dict/list outputs
                    self.log_json(test_id, output, title="Test Output", level="DEBUG")
                else:
                    output_str = str(output)
                    # Truncate very long outputs
                    if len(output_str) > 5000:
                        output_str = output_str[:5000] + "\n... (truncated)"
                    self.log(test_id, f"Output:\n{output_str}", level="DEBUG")
            
            # Log error using structured failure reporting
            error = result.get("error")
            if error:
                # Extract failure message (first line or summary)
                error_lines = str(error).strip().split('\n')
                failure_message = error_lines[0] if error_lines else str(error)
                
                # Check if we have a full stack trace
                if len(error_lines) > 1 or 'Traceback' in str(error):
                    # Use structured failure logging with traceback
                    failure_stacktrace = str(error)
                    self.log_failure(
                        test_id,
                        error_message=failure_message,
                        traceback=failure_stacktrace,
                        details={"result_keys": list(result.keys())}
                    )
                else:
                    # Simple error without traceback
                    self.log_error(test_id, f"❌ Error: {failure_message}")
            
            # Log test status
            test_passed = result.get("test_passed")
            if test_passed is True:
                self.log(test_id, "✅ Test PASSED", level="INFO")
            elif test_passed is False:
                self.log_error(test_id, "❌ Test FAILED")
                # If we haven't logged a failure message yet, log generic failure
                if not error:
                    self.log_error(test_id, "Test assertions failed")
            
            return True
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error logging result for {test_id}: {e}")
            return False
    
    def report_suite_summary(self, suite_result: Dict[str, Any]) -> None:
        """
        Report suite summary (optional, for logging purposes).
        
        Args:
            suite_result: SuiteResult dict with summary statistics
        """
        if not self.active or not self.logger:
            return
        
        self.logger.info(
            f"Suite '{suite_result.get('suite_name')}': "
            f"Total={suite_result.get('total')}, "
            f"Passed={suite_result.get('passed')}, "
            f"Failed={suite_result.get('failed')}, "
            f"Success Rate={suite_result.get('success_rate', 0):.1f}%"
        )
    
    def _map_status(self, result: Dict[str, Any]) -> str:
        """
        Map test framework result to ReportPortal status.
        
        Args:
            result: Test result dictionary
            
        Returns:
            RP status string (PASSED/FAILED/SKIPPED/INTERRUPTED)
        """
        # Check if test passed
        test_passed = result.get("test_passed")
        
        if test_passed is True:
            return "PASSED"
        elif test_passed is False:
            return "FAILED"
        
        # Check for errors
        if result.get("error"):
            return "FAILED"
        
        # Check success flag
        if result.get("success") is False:
            return "FAILED"
        elif result.get("success") is True:
            return "PASSED"
        
        # Check for skipped status
        if result.get("skipped"):
            return "SKIPPED"
        
        # Default to PASSED if no clear failure
        return "PASSED"
    
    def close(self) -> None:
        """Close the reporter and cleanup."""
        if self.client:
            try:
                # Close the HTTP session
                if hasattr(self.client, 'session'):
                    self.client.session.close()
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Error closing reporter: {e}")
        
        self._active = False


# Convenience function for quick setup
def create_reporter(logger=None) -> Optional[ReportPortalReporter]:
    """
    Create a ReportPortal reporter if enabled.
    
    Returns None if ReportPortal is not enabled or not available.
    """
    return ReportPortalReporter.from_env(logger)
