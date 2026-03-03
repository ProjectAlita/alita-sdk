#!/usr/bin/env python3
"""
Standalone runner for document loader tests.

Usage:
  python run_tests.py run                              # run all tests
  python run_tests.py run AlitaCSVLoader               # run one loader
  python run_tests.py run AlitaCSVLoader csv_simple    # run one input
  python run_tests.py run AlitaCSVLoader csv_simple -c 1  # single config
  python run_tests.py run --json                       # JSON output

  python run_tests.py list                             # show discovered tests

  python run_tests.py generate AlitaExcelLoader document_index
  python run_tests.py generate AlitaExcelLoader document_index --force
  python run_tests.py generate AlitaExcelLoader document_index -c 0
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

# Allow running from anywhere — resolve project root from script location:
# run_tests.py  →  .alita/tests/loader_tests/
# project root  →  ../../../
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DATA_DIR = SCRIPT_DIR


def _runner():
    from alita_sdk.cli.loader_test_runner import (
        LoaderTestInput,
        discover_loader_tests,
        format_results_json,
        format_results_text,
        generate_expected_outputs,
        run_all_tests,
        run_input_tests,
    )
    return locals()  # just a way to lazy-import; we use the module directly


# ---------------------------------------------------------------------------
# sub-commands
# ---------------------------------------------------------------------------

def cmd_run(args):
    from alita_sdk.cli.loader_test_runner import (
        LoaderTestInput,
        format_results_json,
        format_results_text,
        run_all_tests,
        run_input_tests,
    )

    base_dir = DATA_DIR
    loader_name = args.loader
    input_name = args.input
    config_index = args.config

    run_dir = None

    if not loader_name or args.all:
        # run everything (optionally filtered by loader/input if passed with --all)
        all_results, run_dir = run_all_tests(
            base_dir=base_dir,
            loader_filter=loader_name if not args.all else None,
            input_filter=input_name if not args.all else None,
            config_index=config_index,
        )
    elif loader_name and not input_name:
        all_results, run_dir = run_all_tests(
            base_dir=base_dir,
            loader_filter=loader_name,
            config_index=config_index,
        )
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = SCRIPT_DIR / "test_results" / f"output_{timestamp}"
        input_json_path = base_dir / loader_name / "input" / f"{input_name}.json"
        if not input_json_path.exists():
            print(f"ERROR: Input file not found: {input_json_path}", file=sys.stderr)
            sys.exit(1)
        test_input = LoaderTestInput.from_file(input_json_path)
        run_output_dir = run_dir / loader_name
        results = run_input_tests(
            loader_name=loader_name,
            input_name=input_name,
            test_input=test_input,
            base_dir=base_dir,
            input_json_path=input_json_path,
            run_output_dir=run_output_dir,
            config_index=config_index,
        )
        all_results = {loader_name: results}

    if not all_results:
        print("No tests found.", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(format_results_json(all_results, run_dir))
    else:
        print(format_results_text(all_results, run_dir))

    has_failure = any(
        not r.passed or r.error
        for rs in all_results.values()
        for r in rs
    )
    sys.exit(1 if has_failure else 0)


def cmd_list(args):
    from alita_sdk.cli.loader_test_runner import discover_loader_tests

    base_dir = DATA_DIR
    discovery = discover_loader_tests(base_dir)

    if not discovery:
        print("No tests discovered.")
        return

    total = 0
    for loader_name, inputs in sorted(discovery.items()):
        print(f"\n{loader_name}")
        print("-" * len(loader_name))
        for input_name, test_input in sorted(inputs.items()):
            baseline_dir = base_dir / loader_name / "output"
            statuses = []
            for i in range(len(test_input.configs)):
                path = baseline_dir / f"{input_name}_config_{i}.json"
                statuses.append(f"{i}:{'ok' if path.exists() else 'no baseline'}")
            print(f"  {input_name}.json  [{len(test_input.configs)} configs]  " + "  ".join(statuses))
            total += len(test_input.configs)

    print(f"\nTotal: {total} test case(s)")


def cmd_generate(args):
    from alita_sdk.cli.loader_test_runner import LoaderTestInput, generate_expected_outputs

    base_dir = DATA_DIR
    loader_name = args.loader
    input_name = args.input
    input_json_path = base_dir / loader_name / "input" / f"{input_name}.json"

    if not input_json_path.exists():
        print(f"ERROR: Input file not found: {input_json_path}", file=sys.stderr)
        sys.exit(1)

    test_input = LoaderTestInput.from_file(input_json_path)

    try:
        written, output_dir = generate_expected_outputs(
            loader_name=loader_name,
            input_name=input_name,
            test_input=test_input,
            base_dir=base_dir,
            input_json_path=input_json_path,
            config_index=args.config,
            force=args.force,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Output dir: {output_dir.relative_to(base_dir)}")
    for p in written:
        print(f"  Wrote {p.name}")
    if not written:
        print("  Nothing written (all baselines exist; use --force to overwrite).")
    else:
        print(f"Generated {len(written)} baseline file(s).")


# ---------------------------------------------------------------------------
# argument parsing
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        prog="run_tests.py",
        description="Document loader test runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # --- run ---
    p_run = sub.add_parser("run", help="Run loader tests and compare against baselines")
    p_run.add_argument("loader", nargs="?", default=None, help="Loader class name (e.g. AlitaCSVLoader)")
    p_run.add_argument("input", nargs="?", default=None, help="Input name without .json (e.g. csv_simple)")
    p_run.add_argument("-c", "--config", type=int, default=None, metavar="N", help="Only run config at index N")
    p_run.add_argument("--all", action="store_true", help="Run every test (ignore positional args)")
    p_run.add_argument("--json", action="store_true", help="Output results as JSON")
    p_run.set_defaults(func=cmd_run)

    # --- list ---
    p_list = sub.add_parser("list", help="List discovered tests and baseline status")
    p_list.set_defaults(func=cmd_list)

    # --- generate ---
    p_gen = sub.add_parser("generate", help="Generate baseline output files for a loader input")
    p_gen.add_argument("loader", help="Loader class name (e.g. AlitaExcelLoader)")
    p_gen.add_argument("input", help="Input name without .json (e.g. document_index)")
    p_gen.add_argument("-c", "--config", type=int, default=None, metavar="N", help="Only generate config at index N")
    p_gen.add_argument("--force", action="store_true", help="Overwrite existing baselines")
    p_gen.set_defaults(func=cmd_generate)

    return parser


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)
