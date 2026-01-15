#!/usr/bin/env python3
"""
Test Management Script

Unified runner for Alita SDK pipeline tests. Replaces run_test.sh and run_all_suites.sh.
Handles setup, seeding, execution, and cleanup for individual tests or entire suites.
"""

import argparse
import sys
import os
import subprocess
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from contextlib import contextmanager

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.status import Status
    
    console = Console()
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

# Import helper libraries
# Ensure script directory is in path to import local modules
SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.append(str(SCRIPT_DIR))
sys.path.append(str(SCRIPT_DIR / "scripts"))

from scripts import setup, seed_pipelines, cleanup, generate_report

# Constants
DEFAULT_SUITES = ["github_toolkit", "state_retrieval", "structured_output"]
DEFAULT_ENV_FILE = ".env.test"
COLORS = {
    "RED": "\033[0;31m",
    "GREEN": "\033[0;32m",
    "YELLOW": "\033[1;33m",
    "BLUE": "\033[0;34m",
    "NC": "\033[0m",
}

@contextmanager
def redirect_to_file(path: Path):
    """Redirect stdout and stderr to a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = f
        sys.stderr = f
        try:
            yield
        except Exception as e:
            # Print exception to file before propagating
            print(f"ERROR: {e}", file=f)
            import traceback
            traceback.print_exc(file=f)
            raise
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

def print_color(text: str, color: str = "NC", end: str = "\n"):
    """Print text in color."""
    if HAS_RICH and color != "NC":
        style_map = {
            "RED": "bold red",
            "GREEN": "bold green",
            "YELLOW": "bold yellow",
            "BLUE": "bold blue",
            "NC": "default"
        }
        rich_style = style_map.get(color, "default")
        console.print(text, style=rich_style, end=end)
    else:
        print(f"{COLORS.get(color, '')}{text}{COLORS['NC']}", end=end)

def print_header(text: str):
    """Print a header block."""
    if HAS_RICH:
        console.print()
        console.rule(f"[bold blue]{text}", style="blue")
        console.print()
    else:
        print_color("═══════════════════════════════════════════════════════════", "BLUE")
        print_color(f"  {text}", "BLUE")
        print_color("═══════════════════════════════════════════════════════════\n", "BLUE")

def run_subprocess(cmd: List[str], cwd: Path = SCRIPT_DIR, env: Dict[str, str] = None, capture_output: bool = False, verbose: bool = False, log_file: Path = None) -> subprocess.CompletedProcess:
    """Run a subprocess with proper error handling and logging."""
    if verbose:
        print_color(f"Executing: {' '.join(cmd)}", "BLUE")
    
    try:
        # If log_file is provided, open it and pipe stdout/stderr to it AND stream to current stdout/stderr if not capturing
        if log_file:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(log_file, "w") as f:
                if capture_output:
                     pass 
                else:
                    process = subprocess.Popen(
                        cmd,
                        cwd=cwd,
                        env=env or os.environ.copy(),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT, # Redirect stderr to stdout
                        text=True,
                        bufsize=1
                    )
                    
                    output_lines = []
                    for line in process.stdout:
                        print(line, end="") # Print to console
                        f.write(line) # Write to file
                        output_lines.append(line)
                    
                    process.wait()
                    
                    return subprocess.CompletedProcess(args=cmd, returncode=process.returncode, stdout="".join(output_lines), stderr="")

        # Default behavior if no log_file
        result = subprocess.run(
            cmd,
            cwd=cwd,
            env=env or os.environ.copy(),
            check=False,
            capture_output=capture_output,
            text=True
        )
        return result
    except Exception as e:
        print_color(f"Error executing command: {e}", "RED")
        sys.exit(1)

class TestRunner:
    def __init__(self, args):
        self.args = args
        self.env_file = Path(args.env_file).resolve()
        self.verbose = args.verbose
        self.results_dir = Path(args.output_dir).resolve() if hasattr(args, 'output_dir') else Path("test_results").resolve()

    def _get_python_cmd(self) -> List[str]:
        return [sys.executable]

    def _run_with_spinner(self, task_name: str, func, log_path: Path, *args, **kwargs) -> bool:
        """Run a task with a spinner and logging."""
        result = {}
        if HAS_RICH and not self.verbose:
            with console.status(f"[bold yellow]{task_name}...", spinner="dots"):
                with redirect_to_file(log_path):
                    try:
                        result = func(*args, **kwargs)
                    except Exception as e:
                         print(f"\nEXCEPTION: {e}")
                         return False

            if result.get("success"):
                console.print(f"[bold green]✓ {task_name} completed[/bold green]")
                return True
            else:
                console.print(f"[bold red]✗ {task_name} failed[/bold red] (see {log_path})")
                return False
        else:
            # Fallback or verbose mode
            print_color(f"▶ {task_name}...", "YELLOW")
            with redirect_to_file(log_path):
                try:
                    result = func(*args, **kwargs)
                except Exception as e:
                    print(f"\nEXCEPTION: {e}")
                    result = {"success": False}
            
            if result.get("success"):
                print_color(f"✓ {task_name} completed", "GREEN")
                return True
            else:
                print_color(f"✗ {task_name} failed (see {log_path})", "RED")
                return False

    def setup(self, suite_spec: str) -> bool:
        safe_suite_name = suite_spec.replace(":", "_")
        log_dir = self.results_dir / safe_suite_name
        log_path = log_dir / "setup.log"
        
        return self._run_with_spinner(
            f"Running setup for {suite_spec}",
            setup.run,
            log_path,
            folder=suite_spec,
            env_file=self.env_file if self.env_file.exists() else None,
            output_env=self.env_file,
            verbose=self.verbose
        )

    def seed(self, suite_spec: str, pattern: str = "") -> bool:
        safe_suite_name = suite_spec.replace(":", "_")
        log_dir = self.results_dir / safe_suite_name
        log_path = log_dir / "seed.log"
        
        pattern_list = pattern.split(",") if pattern else None
        
        return self._run_with_spinner(
            f"Seeding pipelines for {suite_spec}",
            seed_pipelines.run,
            log_path,
            folder=suite_spec,
            env_file=self.env_file,
            pattern=pattern_list,
            verbose=self.verbose
        )

    def run_tests(self, suite_spec: str, pattern: str = "", timeout: int = 120, json_output: bool = False) -> Optional[Dict]:
        print_color(f"▶ Running test(s) for {suite_spec} (pattern: '{pattern}')...", "YELLOW")
        safe_suite_name = suite_spec.replace(":", "_")
        log_dir = self.results_dir / safe_suite_name
        log_dir.mkdir(parents=True, exist_ok=True)
        results_json_path = log_dir / "results.json"

        # Load env vars from file to pass to subprocess
        env = os.environ.copy()
        if self.env_file.exists():
            with open(self.env_file) as f:
                for line in f:
                    if line.strip() and not line.startswith('#'):
                        key, _, value = line.partition('=')
                        if key and value:
                            env[key.strip()] = value.strip()

        cmd = self._get_python_cmd() + [
            "scripts/run_suite.py", 
            suite_spec,
            "--timeout", str(timeout),
            "--env-file", str(self.env_file)
        ]
        
        if pattern:
            cmd.extend(["--pattern", pattern])
        if self.verbose:
            cmd.append("--verbose")
        if json_output:
            cmd.append("--json")
            
        # Always output full results to results.json
        cmd.extend(["--output-json", str(log_dir / "results.json")])
            
        log_file = log_dir / "run.log" if not json_output else None

        # Keeping subprocess for run_suite for now as it wasn't targeted for lib refactor
        result = run_subprocess(cmd, env=env, capture_output=json_output, verbose=self.verbose, log_file=log_file)
        
        if json_output:
             if result.returncode == 0:
                try:
                    data = json.loads(result.stdout)
                    # Automatically generate HTML report if JSON was successful
                    if results_json_path.exists():
                         report_path = generate_report.run(results_json_path)
                         if report_path and self.verbose:
                             print_color(f"Report generated: {report_path}", "BLUE")
                    
                    return data
                except json.JSONDecodeError:
                    print_color("Error parsing JSON output from run_suite.py", "RED")
                    with open(log_dir / "run_error.log", "w") as f:
                        f.write(result.stdout)
                    return None
             else:
                 with open(log_dir / "run.log", "w") as f:
                     f.write(result.stdout + "\n" + result.stderr)
                 return None
        
        # If running normally (not json_output), we still might want to generate report 
        # but run_suite doesn't output JSON unless asked. 
        # So we only generate report if run_suite was told to --output-json (which we added)
        if results_json_path.exists():
             report_path = generate_report.run(results_json_path)
             if report_path:
                 print_color(f"Report generated: {report_path}", "BLUE")
        
        return result.returncode == 0

    def cleanup(self, suite_spec: str) -> bool:
        safe_suite_name = suite_spec.replace(":", "_")
        log_dir = self.results_dir / safe_suite_name
        log_path = log_dir / "cleanup.log"
        
        return self._run_with_spinner(
            f"Running cleanup for {suite_spec}",
            cleanup.run,
            log_path,
            folder=suite_spec,
            env_file=self.env_file,
            verbose=self.verbose,
            skip_pipelines=False
        )

def command_single(args):
    """Handle 'single' command - single test execution."""
    runner = TestRunner(args)

    if not args.suite:
        print_color("Error: Suite argument is required for single test run.", "RED")
        sys.exit(1)

    print_header(f"Running Single Test: {args.pattern}\nSuite: {args.suite}")

    do_all = args.all
    do_setup = args.setup or do_all
    do_seed = args.seed or do_all
    do_cleanup = args.cleanup or do_all

    if do_setup:
        if not runner.setup(args.suite):
            sys.exit(1)

    if not runner.env_file.exists():
        print_color(f"Error: Environment file not found: {runner.env_file}", "RED")
        print_color("Hint: Run with --setup first, or check --env-file", "YELLOW")
        sys.exit(1)

    if do_seed:
        if not runner.seed(args.suite, args.pattern):
            sys.exit(1)

    success = runner.run_tests(args.suite, args.pattern, args.timeout)
    
    if do_cleanup:
        runner.cleanup(args.suite)

    if not success:
        sys.exit(1)

def command_suite(args):
    """Handle 'suite' command - full suite execution."""
    runner = TestRunner(args)
    suites = args.suites if args.suites else DEFAULT_SUITES

    print_header(f"Test Suites Execution\nSuites: {', '.join(suites)}")

    runner.results_dir.mkdir(parents=True, exist_ok=True)
    
    stats = {
        "passed": 0,
        "failed": 0,
        "suites_run": 0,
        "suites_failed": []
    }

    if not args.skip_initial_cleanup:
        print_color("Initial Cleanup...", "BLUE")
        for suite in suites:
             runner.cleanup(suite)

    for suite in suites:
        print_color(f"\nRunning Suite: {suite}", "BLUE")
        start_time = time.time()
        
        suite_success = True
        
        # Setup
        if not args.skip_setup:
            if not runner.setup(suite):
                suite_success = False
        
        # Seed
        if suite_success:
            if not runner.seed(suite):
                suite_success = False
        
        # Run
        if suite_success:
            results = runner.run_tests(suite, json_output=True)
            if results:
                passed = results.get('passed', 0)
                failed = results.get('failed', 0)
                stats["passed"] += passed
                stats["failed"] += failed
                
                if HAS_RICH:
                    console.print(f"  Results: [green]{passed} passed[/green], [red]{failed} failed[/red]")
                else:
                    print_color(f"  Results: {passed} passed, {failed} failed", "NC")
                
                if failed > 0:
                    suite_success = False
            else:
                suite_success = False
                print_color("  Test execution failed to produce results.", "RED")

        # Cleanup
        if not args.skip_cleanup:
            runner.cleanup(suite)
        
        duration = time.time() - start_time
        stats["suites_run"] += 1
        
        if not suite_success:
            stats["suites_failed"].append(suite)
            print_color(f"✗ Suite {suite} failed in {duration:.2f}s", "RED")
            if args.stop_on_failure:
                break
        else:
            print_color(f"✓ Suite {suite} completed in {duration:.2f}s", "GREEN")

    print_header("Final Summary")
    print_color(f"Total Tests: {stats['passed'] + stats['failed']}", "NC")
    print_color(f"Passed: {stats['passed']}", "GREEN")
    print_color(f"Failed: {stats['failed']}", "RED")
    
    if stats["suites_failed"]:
        print_color(f"Failed Suites: {', '.join(stats['suites_failed'])}", "RED")
        sys.exit(1)
    else:
        print_color("All suites passed!", "GREEN")
        sys.exit(0)

def main():
    parser = argparse.ArgumentParser(description="Alita SDK Test Manager")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--env-file", default=DEFAULT_ENV_FILE, help="Environment file to use")
    parser.add_argument("--output-dir", default="test_results", help="Directory for logs and results")
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # 'run' command
    run_parser = subparsers.add_parser("run", help="Run individual test(s)")
    run_parser.add_argument("suite", help="Suite folder name")
    run_parser.add_argument("pattern", nargs="?", default="", help="Test name pattern")
    run_parser.add_argument("--setup", action="store_true", help="Run setup before testing")
    run_parser.add_argument("--seed", action="store_true", help="Seed pipelines before running")
    run_parser.add_argument("--cleanup", action="store_true", help="Run cleanup after testing")
    run_parser.add_argument("--all", action="store_true", help="Run full workflow (setup+seed+run+cleanup)")
    run_parser.add_argument("--timeout", type=int, default=120, help="Execution timeout per pipeline")

    # 'suites' command
    suite_parser = subparsers.add_parser("suites", help="Run entire test suites")
    suite_parser.add_argument("suites", nargs="*", help="List of suites to run (default: all)")
    suite_parser.add_argument("--skip-setup", action="store_true", help="Skip setup step")
    suite_parser.add_argument("--skip-cleanup", action="store_true", help="Skip per-suite cleanup step")
    suite_parser.add_argument("--skip-initial-cleanup", action="store_true", help="Skip global initial cleanup")
    suite_parser.add_argument("--stop-on-failure", action="store_true", help="Stop execution on first suite failure")

    args = parser.parse_args()

    if args.command == "run":
        command_single(args)
    elif args.command == "suites":
        command_suite(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
