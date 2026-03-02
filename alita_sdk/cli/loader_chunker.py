"""
CLI command group: alita loader-chunker
Commands: run, list, generate-expected
"""

import sys
from pathlib import Path

import click


DEFAULT_DATA_DIR = ".alita/tests/loader_tests/data"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _resolve_data_dir(data_dir: str) -> Path:
    p = Path(data_dir)
    if not p.is_absolute():
        p = Path.cwd() / p
    return p


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------

@click.group(name="loader-chunker")
def loader_chunker():
    """Document loader chunker test commands."""


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------

@loader_chunker.command("run")
@click.argument("loader_name", required=False, default=None)
@click.argument("input_name", required=False, default=None)
@click.option(
    "--all", "run_all",
    is_flag=True,
    default=False,
    help="Run every discovered test (overrides positional args).",
)
@click.option(
    "--config-index",
    type=int,
    default=None,
    metavar="N",
    help="Only run config at index N (0-based).",
)
@click.option(
    "--data-dir",
    default=DEFAULT_DATA_DIR,
    show_default=True,
    help="Root directory for loader tests.",
)
@click.option(
    "--output",
    "output_fmt",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default="text",
    show_default=True,
    help="Output format.",
)
def run_tests(loader_name, input_name, run_all, config_index, data_dir, output_fmt):
    """Run document loader tests.

    Examples:

    \b
      alita loader-chunker run                          # same as --all
      alita loader-chunker run AlitaCSVLoader           # all csv inputs
      alita loader-chunker run AlitaCSVLoader csv_simple
      alita loader-chunker run AlitaCSVLoader csv_simple --config-index 1
      alita loader-chunker run --all --output json
    """
    from .loader_test_runner import (
        discover_loader_tests,
        run_all_tests,
        run_input_tests,
        format_results_text,
        format_results_json,
        LoaderTestInput,
    )

    base_dir = _resolve_data_dir(data_dir)

    if not base_dir.is_dir():
        click.echo(f"Data directory not found: {base_dir}", err=True)
        sys.exit(1)

    # No args given → treat as --all
    if not run_all and not loader_name:
        run_all = True

    run_dir = None
    if run_all or not loader_name:
        all_results, run_dir = run_all_tests(
            base_dir=base_dir,
            loader_filter=None if run_all else loader_name,
            input_filter=None if run_all else input_name,
            config_index=config_index,
        )
    elif loader_name and not input_name:
        all_results, run_dir = run_all_tests(
            base_dir=base_dir,
            loader_filter=loader_name,
            config_index=config_index,
        )
    else:
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = base_dir.parent / f"output_{timestamp}"
        input_json_path = base_dir / loader_name / "input" / f"{input_name}.json"
        if not input_json_path.exists():
            click.echo(f"Input file not found: {input_json_path}", err=True)
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
        click.echo("No tests found.", err=True)
        sys.exit(1)

    if output_fmt == "json":
        click.echo(format_results_json(all_results, run_dir))
    else:
        click.echo(format_results_text(all_results, run_dir))

    # Non-zero exit when any test failed
    has_failure = any(
        not r.passed or r.error
        for rs in all_results.values()
        for r in rs
    )
    if has_failure:
        sys.exit(1)


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------

@loader_chunker.command("list")
@click.option(
    "--data-dir",
    default=DEFAULT_DATA_DIR,
    show_default=True,
    help="Root directory for loader tests.",
)
def list_tests(data_dir):
    """List all discovered loader tests."""
    from .loader_test_runner import discover_loader_tests, find_latest_output_dir, find_all_output_dirs, find_baseline_file

    base_dir = _resolve_data_dir(data_dir)

    if not base_dir.is_dir():
        click.echo(f"Data directory not found: {base_dir}", err=True)
        sys.exit(1)

    discovery = discover_loader_tests(base_dir)

    if not discovery:
        click.echo("No tests discovered.")
        return

    total = 0
    for loader_name, inputs in sorted(discovery.items()):
        latest_dir = find_latest_output_dir(base_dir, loader_name)
        all_dirs = find_all_output_dirs(base_dir, loader_name)
        dir_label = f"  [latest baseline: {latest_dir.name}]" if latest_dir else "  [no baselines yet]"
        click.echo(f"\n{loader_name}/{dir_label}")
        if len(all_dirs) > 1:
            click.echo(f"  ({len(all_dirs)} baseline sets total)")
        for input_name, test_input in sorted(inputs.items()):
            config_statuses = []
            for i in range(len(test_input.configs)):
                filename = f"{input_name}_config_{i}.json"
                found = find_baseline_file(base_dir, loader_name, filename)
                status = f"[ok:{found.parent.name}]" if found else "[no baseline]"
                config_statuses.append(f"{i}:{status}")
            configs_str = "  ".join(config_statuses)
            click.echo(f"  {input_name}.json  [{len(test_input.configs)} configs]  {configs_str}")
            total += len(test_input.configs)

    click.echo(f"\nTotal: {total} test case(s)")


# ---------------------------------------------------------------------------
# generate-expected
# ---------------------------------------------------------------------------

@loader_chunker.command("generate-expected")
@click.argument("loader_name")
@click.argument("input_name")
@click.option(
    "--config-index",
    type=int,
    default=None,
    metavar="N",
    help="Only generate baseline for config at index N.",
)
@click.option(
    "--data-dir",
    default=DEFAULT_DATA_DIR,
    show_default=True,
    help="Root directory for loader tests.",
)
def generate_expected(loader_name, input_name, config_index, data_dir):
    """Generate expected (baseline) output files for a loader input.

    Each invocation creates a new timestamped directory:
      <data-dir>/output_<LOADER>_<YYYYMMDD_HHMMSS>/

    Example:

    \b
      alita loader-chunker generate-expected AlitaCSVLoader csv_simple
      alita loader-chunker generate-expected AlitaMarkdownLoader markdown_headers
    """
    from .loader_test_runner import LoaderTestInput, generate_expected_outputs

    base_dir = _resolve_data_dir(data_dir)
    input_json_path = base_dir / loader_name / "input" / f"{input_name}.json"

    if not input_json_path.exists():
        click.echo(f"Input file not found: {input_json_path}", err=True)
        sys.exit(1)

    test_input = LoaderTestInput.from_file(input_json_path)

    try:
        written, output_dir = generate_expected_outputs(
            loader_name=loader_name,
            input_name=input_name,
            test_input=test_input,
            base_dir=base_dir,
            input_json_path=input_json_path,
            config_index=config_index,
        )
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    click.echo(f"Output dir: {output_dir.relative_to(base_dir)}")
    for p in written:
        click.echo(f"  Wrote {p.name}")
    click.echo(f"Generated {len(written)} baseline file(s).")
