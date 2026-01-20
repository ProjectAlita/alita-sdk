#!/usr/bin/env python3
"""
Execute all test suites sequentially - Python version for debugging.

This script mirrors run_all_suites.sh functionality but allows Python debugging.

Usage:
    python run_all_suites.py [OPTIONS] [SUITE...]

Examples:
    python run_all_suites.py                              # Run all suites
    python run_all_suites.py -v github_toolkit            # Run with verbose output
    python run_all_suites.py --local github_toolkit       # Run locally (no backend)
    python run_all_suites.py --skip-cleanup               # Run all but skip cleanup
    python run_all_suites.py --stop-on-failure github_toolkit state_retrieval
"""

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

# Script directory
SCRIPT_DIR = Path(__file__).parent
SCRIPTS_DIR = SCRIPT_DIR / "scripts"

# Add scripts directory to path for imports
sys.path.insert(0, str(SCRIPTS_DIR))

# Default suites
DEFAULT_SUITES = ["github_toolkit", "state_retrieval", "structured_output"]


# Colors for output (ANSI codes)
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color


@dataclass
class SuiteResult:
    """Result of running a test suite."""
    status: str = "NOT_RUN"
    passed: int = 0
    failed: int = 0
    duration: float = 0.0
    error: Optional[str] = None


def print_header(text: str):
    """Print a formatted header."""
    print(f"\n{Colors.BLUE}═══════════════════════════════════════════════════════════{Colors.NC}")
    print(f"{Colors.BLUE}  {text}{Colors.NC}")
    print(f"{Colors.BLUE}═══════════════════════════════════════════════════════════{Colors.NC}\n")


def print_step(text: str):
    """Print a step indicator."""
    print(f"{Colors.YELLOW}▶ {text}{Colors.NC}")


def print_success(text: str):
    """Print a success message."""
    print(f"{Colors.GREEN}✓ {text}{Colors.NC}")


def print_error(text: str):
    """Print an error message."""
    print(f"{Colors.RED}✗ {text}{Colors.NC}")


def parse_suite_spec(suite_spec: str) -> tuple:
    """Parse suite specification into folder and optional pipeline file."""
    if ':' in suite_spec:
        folder, pipeline_file = suite_spec.split(':', 1)
        return folder, pipeline_file
    return suite_spec, None


def run_suite_remote(
    suite_spec: str,
    output_dir: Path,
    verbose: bool,
    skip_setup: bool = False,
    skip_cleanup: bool = False,
) -> SuiteResult:
    """Run a suite using remote backend."""
    suite_dir, pipeline_file = parse_suite_spec(suite_spec)
    start_time = time.time()
    result = SuiteResult()
    
    print_header(f"Running Test Suite: {suite_spec}")
    
    # Validate suite directory
    suite_path = SCRIPT_DIR / suite_dir
    if not suite_path.is_dir():
        print_error(f"Suite directory not found: {suite_dir}")
        result.status = "FAILED"
        return result
    
    config_file = pipeline_file or "pipeline.yaml"
    if not (suite_path / config_file).exists():
        print_error(f"{config_file} not found in {suite_dir}/")
        result.status = "FAILED"
        return result
    
    # Create output directory
    suite_output_name = suite_spec.replace(':', '_')
    suite_output_dir = output_dir / suite_output_name
    suite_output_dir.mkdir(parents=True, exist_ok=True)
    
    verbose_args = ["--verbose"] if verbose else []
    
    # Step 1: Setup
    if not skip_setup:
        print_step(f"Step 1/4: Running setup for {suite_spec}")
        cmd = [
            sys.executable, str(SCRIPTS_DIR / "setup.py"),
            suite_spec,
            "--output-env", ".env",
        ] + verbose_args
        
        with open(suite_output_dir / "setup.log", "w") as log:
            proc = subprocess.run(cmd, cwd=SCRIPT_DIR, stdout=log, stderr=subprocess.STDOUT)
        
        if proc.returncode != 0:
            print_error(f"Setup failed - see {suite_output_dir}/setup.log")
            result.status = "SETUP_FAILED"
            return result
        print_success("Setup completed")
    else:
        print("  Skipping setup (using existing environment)")
    
    # Step 2: Seed pipelines
    print_step(f"Step 2/4: Seeding pipelines for {suite_spec}")
    cmd = [
        sys.executable, str(SCRIPTS_DIR / "seed_pipelines.py"),
        suite_spec,
        "--env-file", ".env",
    ] + verbose_args
    
    with open(suite_output_dir / "seed.log", "w") as log:
        proc = subprocess.run(cmd, cwd=SCRIPT_DIR, stdout=log, stderr=subprocess.STDOUT)
    
    if proc.returncode != 0:
        print_error(f"Seeding failed - see {suite_output_dir}/seed.log")
        result.status = "SEED_FAILED"
        return result
    print_success("Pipelines seeded")
    
    # Step 3: Run tests
    print_step(f"Step 3/4: Running tests for {suite_spec}")
    results_file = suite_output_dir / "results.json"
    
    cmd = [
        sys.executable, str(SCRIPTS_DIR / "run_suite.py"),
        suite_spec,
        "--json",
    ] + verbose_args
    
    with open(results_file, "w") as stdout_file, open(suite_output_dir / "run.log", "w") as stderr_file:
        proc = subprocess.run(cmd, cwd=SCRIPT_DIR, stdout=stdout_file, stderr=stderr_file)
    
    if proc.returncode != 0:
        print_error(f"Test execution failed - see {suite_output_dir}/run.log")
        result.status = "RUN_FAILED"
    else:
        print_success("Tests completed")
        
        # Parse results
        if results_file.exists():
            try:
                with open(results_file) as f:
                    data = json.load(f)
                result.passed = data.get("passed", 0)
                result.failed = data.get("failed", 0)
                total = data.get("total_tests", 0)
                print(f"  Results: {result.passed} passed, {result.failed} failed (total: {total})")
                
                if result.failed > 0:
                    result.status = "TESTS_FAILED"
                    print_error("Some tests failed")
                else:
                    result.status = "PASSED"
            except Exception as e:
                print_error(f"Failed to parse results: {e}")
                result.status = "RUN_FAILED"
    
    # Step 4: Cleanup
    if not skip_cleanup:
        print_step(f"Step 4/4: Cleaning up {suite_spec}")
        cmd = [
            sys.executable, str(SCRIPTS_DIR / "cleanup.py"),
            suite_spec,
            "--yes",
        ] + verbose_args
        
        with open(suite_output_dir / "cleanup.log", "w") as log:
            proc = subprocess.run(cmd, cwd=SCRIPT_DIR, stdout=log, stderr=subprocess.STDOUT)
        
        if proc.returncode == 0:
            print_success("Cleanup completed")
        else:
            print_error(f"Cleanup failed - see {suite_output_dir}/cleanup.log (continuing anyway)")
    else:
        print("  Skipping cleanup")
    
    result.duration = time.time() - start_time
    print_success(f"Suite {suite_spec} completed in {result.duration:.1f}s")
    
    return result


def run_suite_local(
    suite_spec: str,
    output_dir: Path,
    verbose: bool,
    skip_setup: bool = False,
    skip_cleanup: bool = False,
) -> SuiteResult:
    """Run a suite locally without backend - same flow as remote."""
    suite_dir, pipeline_file = parse_suite_spec(suite_spec)
    start_time = time.time()
    result = SuiteResult()
    
    print_header(f"Running Test Suite (LOCAL): {suite_spec}")
    
    # Validate suite directory
    suite_path = SCRIPT_DIR / suite_dir
    if not suite_path.is_dir():
        print_error(f"Suite directory not found: {suite_dir}")
        result.status = "FAILED"
        return result
    
    config_file = pipeline_file or "pipeline.yaml"
    if not (suite_path / config_file).exists():
        print_error(f"{config_file} not found in {suite_dir}/")
        result.status = "FAILED"
        return result
    
    # Create output directory
    suite_output_name = suite_spec.replace(':', '_')
    suite_output_dir = output_dir / suite_output_name
    suite_output_dir.mkdir(parents=True, exist_ok=True)
    
    verbose_args = ["--verbose"] if verbose else []
    
    # Step 1: Setup (with --local flag)
    if not skip_setup:
        print_step(f"Step 1/3: Running setup for {suite_spec} (local)")
        cmd = [
            sys.executable, str(SCRIPTS_DIR / "setup.py"),
            suite_spec,
            "--output-env", ".env",
            "--local",
        ] + verbose_args
        
        with open(suite_output_dir / "setup.log", "w") as log:
            proc = subprocess.run(cmd, cwd=SCRIPT_DIR, stdout=log, stderr=subprocess.STDOUT)
        
        if proc.returncode != 0:
            print_error(f"Setup failed - see {suite_output_dir}/setup.log")
            result.status = "SETUP_FAILED"
            return result
        print_success("Setup completed")
    else:
        print("  Skipping setup (using existing environment)")
    
    # Step 2: Run tests (with --local flag)
    print_step(f"Step 2/3: Running tests for {suite_spec} (local)")
    results_file = suite_output_dir / "results.json"
    
    cmd = [
        sys.executable, str(SCRIPTS_DIR / "run_suite.py"),
        suite_spec,
        "--json",
        "--local",
    ] + verbose_args
    
    with open(results_file, "w") as stdout_file, open(suite_output_dir / "run.log", "w") as stderr_file:
        proc = subprocess.run(cmd, cwd=SCRIPT_DIR, stdout=stdout_file, stderr=stderr_file)
    
    if proc.returncode != 0:
        print_error(f"Test execution failed - see {suite_output_dir}/run.log")
        result.status = "RUN_FAILED"
    else:
        print_success("Tests completed")
        
        # Parse results
        if results_file.exists():
            try:
                with open(results_file) as f:
                    data = json.load(f)
                result.passed = data.get("passed", 0)
                result.failed = data.get("failed", 0)
                total = data.get("total_tests", 0)
                print(f"  Results: {result.passed} passed, {result.failed} failed (total: {total})")
                
                if result.failed > 0:
                    result.status = "TESTS_FAILED"
                    print_error("Some tests failed")
                else:
                    result.status = "PASSED"
            except Exception as e:
                print_error(f"Failed to parse results: {e}")
                result.status = "RUN_FAILED"
    
    # Step 3: Cleanup (with --local flag)
    if not skip_cleanup:
        print_step(f"Step 3/3: Cleaning up {suite_spec} (local)")
        cmd = [
            sys.executable, str(SCRIPTS_DIR / "cleanup.py"),
            suite_spec,
            "--yes",
            "--local",
        ] + verbose_args
        
        with open(suite_output_dir / "cleanup.log", "w") as log:
            proc = subprocess.run(cmd, cwd=SCRIPT_DIR, stdout=log, stderr=subprocess.STDOUT)
        
        if proc.returncode == 0:
            print_success("Cleanup completed")
        else:
            print_error(f"Cleanup failed - see {suite_output_dir}/cleanup.log (continuing anyway)")
    else:
        print("  Skipping cleanup")
    
    result.duration = time.time() - start_time
    print_success(f"Suite {suite_spec} (LOCAL) completed in {result.duration:.1f}s")
    
    return result


def run_initial_cleanup(suites: List[str], output_dir: Path, verbose: bool):
    """Run cleanup for all suites before starting."""
    print_header("Initial Cleanup")
    print_step("Cleaning up resources from previous runs")
    
    cleanup_failed = False
    verbose_args = ["--verbose"] if verbose else []
    
    for suite_spec in suites:
        suite_dir, _ = parse_suite_spec(suite_spec)
        suite_path = SCRIPT_DIR / suite_dir
        log_name = suite_spec.replace(':', '_')
        
        if suite_path.is_dir() and (suite_path / "pipeline.yaml").exists():
            print(f"  Cleaning up {suite_spec}...")
            cmd = [
                sys.executable, str(SCRIPTS_DIR / "cleanup.py"),
                suite_spec,
                "--yes",
            ] + verbose_args
            
            with open(output_dir / f"{log_name}_initial_cleanup.log", "w") as log:
                proc = subprocess.run(cmd, cwd=SCRIPT_DIR, stdout=log, stderr=subprocess.STDOUT)
            
            if proc.returncode == 0:
                print("    ✓ Cleaned")
            else:
                print(f"    ⚠ Cleanup had issues (see {output_dir}/{log_name}_initial_cleanup.log)")
                cleanup_failed = True
    
    if not cleanup_failed:
        print_success("Initial cleanup completed")
    else:
        print_error("Initial cleanup had some issues but continuing...")
    print()


def print_summary(suites: List[str], results: Dict[str, SuiteResult], total_duration: float):
    """Print execution summary."""
    print_header("Execution Summary")
    
    print("Suite Results:\n")
    print(f"{'SUITE':<20} {'STATUS':<15} {'PASSED':<10} {'FAILED':<10} {'DURATION':<10}")
    print("─" * 70)
    
    for suite_spec in suites:
        result = results.get(suite_spec, SuiteResult())
        status = result.status
        
        # Color code status
        if status == "PASSED":
            status_colored = f"{Colors.GREEN}{status}{Colors.NC}"
        elif status == "TESTS_FAILED":
            status_colored = f"{Colors.YELLOW}{status}{Colors.NC}"
        else:
            status_colored = f"{Colors.RED}{status}{Colors.NC}"
        
        # Truncate suite name if too long
        display_name = suite_spec[:20]
        print(f"{display_name:<20} {status_colored:<24} {result.passed:<10} {result.failed:<10} {result.duration:.1f}s")
    
    print()
    print(f"Total execution time: {total_duration:.1f}s")
    print()
    
    # Check overall success
    all_passed = all(r.status == "PASSED" for r in results.values())
    if all_passed:
        print_success("All suites passed!")
    else:
        print_error("Some suites failed or had errors")
    
    return all_passed


def main():
    parser = argparse.ArgumentParser(
        description='Execute all test suites sequentially with setup, seed, run, and cleanup.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python run_all_suites.py                              # Run all suites
    python run_all_suites.py -v github_toolkit            # Run with verbose output
    python run_all_suites.py --local github_toolkit       # Run locally (no backend)
    python run_all_suites.py --skip-cleanup               # Run all but skip cleanup
    python run_all_suites.py --stop-on-failure github_toolkit state_retrieval
        """
    )
    
    parser.add_argument('suites', nargs='*', default=DEFAULT_SUITES,
                        help=f'Suite(s) to run (default: {" ".join(DEFAULT_SUITES)})')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Enable verbose output')
    parser.add_argument('--local', action='store_true',
                        help='Run tests locally without backend (isolated mode)')
    parser.add_argument('--skip-initial-cleanup', action='store_true',
                        help='Skip cleanup before starting (not recommended)')
    parser.add_argument('--skip-cleanup', action='store_true',
                        help='Skip cleanup after tests')
    parser.add_argument('--skip-setup', action='store_true',
                        help='Skip setup (use existing environment)')
    parser.add_argument('--stop-on-failure', action='store_true',
                        help='Stop executing suites if one fails')
    parser.add_argument('-o', '--output', default='test_results',
                        help='Output directory for results (default: test_results)')
    
    args = parser.parse_args()
    
    # Change to script directory
    os.chdir(SCRIPT_DIR)
    
    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Print header
    print_header("Test Suites Execution")
    print(f"Suites to run: {' '.join(args.suites)}")
    print(f"Output directory: {args.output}")
    if args.local:
        print("Mode: LOCAL (no backend)")
    else:
        print("Mode: REMOTE (backend API)")
    print()
    
    # Initial cleanup (skip for local mode)
    if not args.skip_initial_cleanup and not args.local:
        run_initial_cleanup(args.suites, output_dir, args.verbose)
    else:
        print("Skipping initial cleanup\n")
    
    # Run each suite
    total_start = time.time()
    results: Dict[str, SuiteResult] = {}
    
    for suite_spec in args.suites:
        if args.local:
            result = run_suite_local(
                suite_spec=suite_spec,
                output_dir=output_dir,
                verbose=args.verbose,
                skip_setup=args.skip_setup,
                skip_cleanup=args.skip_cleanup,
            )
        else:
            result = run_suite_remote(
                suite_spec=suite_spec,
                output_dir=output_dir,
                verbose=args.verbose,
                skip_setup=args.skip_setup,
                skip_cleanup=args.skip_cleanup,
            )
        
        results[suite_spec] = result
        
        if result.status == "PASSED":
            print_success(f"✓ {suite_spec}: ALL TESTS PASSED")
        elif result.status == "TESTS_FAILED":
            print_error(f"✗ {suite_spec}: SOME TESTS FAILED")
            if args.stop_on_failure:
                print_error("Stopping execution due to --stop-on-failure")
                break
        else:
            print_error(f"✗ {suite_spec}: SUITE FAILED ({result.status})")
            if args.stop_on_failure:
                print_error("Stopping execution due to --stop-on-failure")
                break
        print()
    
    total_duration = time.time() - total_start
    
    # Print summary
    all_passed = print_summary(args.suites, results, total_duration)
    
    sys.exit(0 if all_passed else 1)


if __name__ == '__main__':
    main()
