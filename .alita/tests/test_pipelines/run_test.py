#!/usr/bin/env python3
"""
Run individual test(s) within a suite - Python version for debugging.

This script mirrors run_test.sh functionality but allows Python debugging.

Usage:
    python run_test.py [OPTIONS] <suite> <pattern>

Examples:
    # First time: setup + seed + run
    python run_test.py --setup --seed github_toolkit update_file

    # Iterative development: just run (after setup/seed done)
    python run_test.py github_toolkit update_file
    python run_test.py github_toolkit 'GH14'

    # Run locally without backend
    python run_test.py --local github_toolkit update_file

    # Full workflow for single test
    python run_test.py --all github_toolkit update_file

    # Re-seed and run (after modifying test YAML)
    python run_test.py --seed github_toolkit update_file

Workflow:
    1. First run:  python run_test.py --setup --seed <suite> <pattern>
    2. Iterate:    python run_test.py <suite> <pattern>  (fast, no setup/seed)
    3. After YAML changes: python run_test.py --seed <suite> <pattern>
    4. Final cleanup: python run_test.py --cleanup <suite> <pattern>
    5. Local testing: python run_test.py --local <suite> <pattern>
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

# Script directory
SCRIPT_DIR = Path(__file__).parent
SCRIPTS_DIR = SCRIPT_DIR / "scripts"

# Add scripts directory to path for imports
sys.path.insert(0, str(SCRIPTS_DIR))

# Colors for output (ANSI codes)
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color


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


def load_env_file(env_file: Path):
    """Load environment variables from a .env file."""
    if not env_file.exists():
        return False
    
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                value = value.strip().strip('"').strip("'")
                os.environ[key] = value
    return True


def run_setup(suite: str, verbose: bool, env_file: str, local: bool = False) -> bool:
    """Run the setup step."""
    print_step("Running setup...")
    
    cmd = [
        sys.executable, str(SCRIPTS_DIR / "setup.py"),
        suite,
        "--output-env", env_file,
    ]
    if verbose:
        cmd.append("--verbose")
    if local:
        cmd.append("--local")
    
    result = subprocess.run(cmd, cwd=SCRIPT_DIR)
    
    if result.returncode == 0:
        print_success("Setup completed")
        return True
    else:
        print_error("Setup failed")
        return False


def run_seed(suite: str, pattern: str, verbose: bool, env_file: str, local: bool = False) -> bool:
    """Run the seed pipelines step."""
    print_step(f"Seeding pipelines matching: '{pattern}'")
    
    cmd = [
        sys.executable, str(SCRIPTS_DIR / "seed_pipelines.py"),
        suite,
        "--env-file", env_file,
        "--pattern", pattern,
    ]
    if verbose:
        cmd.append("--verbose")
    if local:
        cmd.append("--local")
    
    result = subprocess.run(cmd, cwd=SCRIPT_DIR)
    
    if result.returncode == 0:
        print_success("Pipelines seeded")
        return True
    else:
        print_error("Seeding failed")
        return False


def run_tests_remote(suite: str, pattern: str, timeout: int, verbose: bool, env_file: str, local: bool = False) -> int:
    """Run tests using run_suite.py (supports both remote and local modes)."""
    print_step(f"Running test(s) matching: '{pattern}'")
    print()
    
    # Load environment file if exists
    env_path = SCRIPT_DIR / env_file
    if env_path.exists():
        load_env_file(env_path)
    
    cmd = [
        sys.executable, str(SCRIPTS_DIR / "run_suite.py"),
        suite,
        "--pattern", pattern,
        "--timeout", str(timeout),
        "--env-file", env_file,
    ]
    if verbose:
        cmd.append("--verbose")
    if local:
        cmd.append("--local")
    
    result = subprocess.run(cmd, cwd=SCRIPT_DIR)
    
    if result.returncode == 0:
        print()
        print_success("Test execution completed")
    else:
        print()
        print_error("Test execution failed")
    
    return result.returncode


def run_tests_local(suite: str, pattern: str, timeout: int, verbose: bool) -> int:
    """Run tests locally without backend (deprecated - use run_tests_remote with local=True)."""
    print_step("Running tests locally (no backend)...")
    print()
    
    cmd = [
        sys.executable, str(SCRIPTS_DIR / "utils_local.py"),
        suite,
        pattern,
        "--timeout", str(timeout),
    ]
    if verbose:
        cmd.append("--verbose")
    
    result = subprocess.run(cmd, cwd=SCRIPT_DIR)
    
    if result.returncode == 0:
        print()
        print_success("Local test execution completed")
    else:
        print()
        print_error("Local test execution failed")
    
    return result.returncode


def run_cleanup(suite: str, verbose: bool, local: bool = False) -> bool:
    """Run cleanup step."""
    print_step("Running cleanup...")
    
    cmd = [
        sys.executable, str(SCRIPTS_DIR / "cleanup.py"),
        suite,
        "--yes",
    ]
    if verbose:
        cmd.append("--verbose")
    if local:
        cmd.append("--local")
    
    result = subprocess.run(cmd, cwd=SCRIPT_DIR)
    
    if result.returncode == 0:
        print_success("Cleanup completed")
        return True
    else:
        print_error("Cleanup failed (continuing)")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Run individual test(s) within a suite by pattern matching.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # First time: setup + seed + run
  python run_test.py --setup --seed github_toolkit update_file

  # Iterative development: just run (after setup/seed done)
  python run_test.py github_toolkit update_file
  python run_test.py github_toolkit 'GH14'           # Match by name prefix
  python run_test.py github_toolkit 'multiline'      # Partial match

  # Run multiple tests matching pattern
  python run_test.py github_toolkit 'GH1'            # Runs GH1, GH10-GH19

  # Full workflow for single test
  python run_test.py --all github_toolkit update_file

  # Re-seed and run (after modifying test YAML)
  python run_test.py --seed github_toolkit update_file

  # Run locally without backend
  python run_test.py --local github_toolkit update_file

Workflow:
  1. First run:  python run_test.py --setup --seed <suite> <pattern>
  2. Iterate:    python run_test.py <suite> <pattern>  (fast, no setup/seed)
  3. After YAML changes: python run_test.py --seed <suite> <pattern>
  4. Final cleanup: python run_test.py --cleanup <suite> <pattern>
  5. Local testing: python run_test.py --local <suite> <pattern>
        """
    )
    
    parser.add_argument('suite', help='Suite folder name (e.g., github_toolkit)')
    parser.add_argument('pattern', help="Test name pattern to match (e.g., 'update_file', 'GH14')")
    
    parser.add_argument('--setup', action='store_true',
                        help='Run setup before testing (creates toolkit, etc.)')
    parser.add_argument('--seed', action='store_true',
                        help='Seed pipelines before running (required first time)')
    parser.add_argument('--cleanup', action='store_true',
                        help='Run cleanup after testing')
    parser.add_argument('--all', action='store_true',
                        help='Equivalent to --setup --seed --cleanup (full workflow)')
    parser.add_argument('--local', action='store_true',
                        help='Run tests locally without backend (isolated mode)')
    parser.add_argument('--env-file', default='.env',
                        help='Environment file to use (default: .env)')
    parser.add_argument('--timeout', type=int, default=120,
                        help='Execution timeout per pipeline (default: 120)')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Enable verbose output')
    
    args = parser.parse_args()
    
    # Handle --all flag
    if args.all:
        args.setup = True
        args.seed = True
        args.cleanup = True
    
    # Change to script directory
    os.chdir(SCRIPT_DIR)
    
    # Validate suite exists
    suite_dir = SCRIPT_DIR / args.suite
    if not suite_dir.is_dir():
        print_error(f"Suite directory not found: {args.suite}")
        sys.exit(1)
    
    pipeline_config = suite_dir / "pipeline.yaml"
    if not pipeline_config.exists():
        print_error(f"pipeline.yaml not found in {args.suite}/")
        sys.exit(1)
    
    # Print header
    print_header(f"Running Test: {args.pattern}")
    print(f"  Suite: {args.suite}")
    if args.local:
        print(f"  Mode: LOCAL (no backend)")
    else:
        print(f"  Mode: REMOTE (backend API)")
    print()
    
    # Same flow for both LOCAL and REMOTE modes:
    # setup → seed → run tests → cleanup
    
    # Step 1: Setup (optional)
    if args.setup:
        if not run_setup(args.suite, args.verbose, args.env_file, local=args.local):
            sys.exit(1)
        print()
    
    # Check env file exists (required for remote mode, optional for local mode)
    env_path = SCRIPT_DIR / args.env_file
    if not args.local and not env_path.exists():
        print_error(f"Environment file not found: {args.env_file}")
        print(f"{Colors.YELLOW}Hint: Run with --setup first, or specify --env-file{Colors.NC}")
        sys.exit(1)
    
    # Step 2: Seed (optional)
    if args.seed:
        if not run_seed(args.suite, args.pattern, args.verbose, args.env_file, local=args.local):
            sys.exit(1)
        print()
    
    # Step 3: Run tests
    run_status = run_tests_remote(
        suite=args.suite,
        pattern=args.pattern,
        timeout=args.timeout,
        verbose=args.verbose,
        env_file=args.env_file,
        local=args.local,
    )
    
    # Step 4: Cleanup (optional)
    if args.cleanup:
        print()
        run_cleanup(args.suite, args.verbose, local=args.local)
    
    print()
    print_header("Test Run Complete")
    
    sys.exit(run_status)


if __name__ == '__main__':
    main()
