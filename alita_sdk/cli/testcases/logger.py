"""
Test execution logging utilities.

Provides the TestLogCapture context manager for capturing console output to log files.
"""

from pathlib import Path
from datetime import datetime
from typing import Optional

from rich.console import Console


class TestLogCapture:
    """
    Context manager to capture console output to a log file.
    Creates a single log file for the entire test execution session.
    Strips Rich markup for plain text output with UTF-8 encoding.
    """
    
    def __init__(self, results_dir: Path, session_name: str, console: Optional[Console] = None):
        """
        Initialize log capture.
        
        Args:
            results_dir: Base results directory
            session_name: Name for this test session
        """
        self.results_dir = results_dir
        self.session_name = session_name
        self.log_file_path = None
        self.was_recording = False
        # Use injected console if provided; otherwise create a dedicated console.
        # Injecting allows other components (e.g., tool-call callbacks) to print to the
        # same console and be captured in the session log.
        self.console: Console = console or Console()
        
    def __enter__(self):
        """Start capturing console output."""
        # Extract toolkit name from session name (e.g., "test-execution-confluence" -> "confluence")
        toolkit_name = self.session_name.replace('test-execution-', '')
        
        # Create toolkit-specific directory
        toolkit_dir = self.results_dir / toolkit_name
        toolkit_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate timestamped filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"{timestamp}.{self.session_name}.txt"
        self.log_file_path = toolkit_dir / log_filename
        
        # Enable recording on this console
        self.was_recording = self.console.record
        self.console.record = True
        
        return self
    
    def print(self, *args, **kwargs):
        """Print to console (both display and recording)."""
        self.console.print(*args, **kwargs)
    
    def status(self, message, **kwargs):
        """Create status spinner and log the message."""
        # Manually record the status message (spinners are transient)
        self.console.print(message)
        # Show spinner (this won't be recorded due to transient nature)
        return self.console.status(message, **kwargs)
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop capturing and save log file."""
        if self.log_file_path:
            # Export recorded text (strips Rich markup)
            plain_text = self.console.export_text()
            
            # Save to file with UTF-8 encoding
            with open(self.log_file_path, 'w', encoding='utf-8') as f:
                f.write(f"Test Execution Session: {self.session_name}\n")
                f.write(f"Timestamp: {datetime.now().isoformat()}\n")
                f.write("=" * 80 + "\n\n")
                f.write(plain_text)
            
            # Restore previous recording state
            self.console.record = self.was_recording
        
        return False
