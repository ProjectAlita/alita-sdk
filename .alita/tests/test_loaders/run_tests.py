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

  python run_tests.py tokenize "Hello world"                    # tokenize text, returns JSON list of token strings
  python run_tests.py tokenize -f file.txt                      # tokenize file content
  python run_tests.py tokenize -f file.txt -m 50                # chunk file with 50 tokens/chunk, 10 token overlap
  python run_tests.py tokenize -f file.txt -m 100 -o 15         # chunk with 100 tokens/chunk, 15 token overlap
  python run_tests.py tokenize -f file.txt -m 50 -out chunks.json  # save chunks as documents to file
"""

import argparse
import logging
import sys
import warnings
from datetime import datetime
from pathlib import Path

# Suppress all warnings and debug output
warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.ERROR)
logging.getLogger('alita_sdk').setLevel(logging.ERROR)
logging.getLogger('git').setLevel(logging.ERROR)
logging.getLogger('paramiko').setLevel(logging.ERROR)

# Allow running from anywhere — resolve project root from script location:
# run_tests.py  →  .alita/tests/test_loaders/
# project root  →  ../../../
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SCRIPT_DIR / "scripts"))

DATA_DIR = SCRIPT_DIR


# ---------------------------------------------------------------------------
# sub-commands
# ---------------------------------------------------------------------------

def cmd_run(args):
    from loader_test_runner import (
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
    from loader_test_runner import discover_loader_tests

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


def cmd_tokenize(args):
    try:
        import tiktoken
    except ImportError:
        print("ERROR: tiktoken not installed. Install with: pip install tiktoken", file=sys.stderr)
        sys.exit(1)

    import json
    
    # Tokenize using tiktoken
    encoding = tiktoken.get_encoding("cl100k_base")
    
    # Get text from file or argument
    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"ERROR: File not found: {file_path}", file=sys.stderr)
            sys.exit(1)
        text = file_path.read_text(encoding='utf-8')
    else:
        text = args.text
    
    # If no chunking params, return token strings
    if args.max_tokens is None:
        token_ids = encoding.encode(text)
        token_strings = [encoding.decode([token_id]) for token_id in token_ids]
        output = json.dumps(token_strings)
        if args.out:
            Path(args.out).write_text(output, encoding='utf-8')
            print(f"Saved {len(token_strings)} tokens to {args.out}")
        else:
            print(output)
        return
    
    # Chunking mode: split text into chunks with overlap
    max_tokens = args.max_tokens
    overlap_tokens = args.overlap if args.overlap is not None else 10
    
    # Tokenize full text
    token_ids = encoding.encode(text)
    total_tokens = len(token_ids)
    
    if total_tokens == 0:
        output = json.dumps([])
        if args.out:
            Path(args.out).write_text(output, encoding='utf-8')
            print(f"Saved 0 chunks to {args.out}")
        else:
            print(output)
        return
    
    # Create chunks with overlap
    chunks = []
    start_idx = 0
    
    while start_idx < total_tokens:
        # Determine end index for this chunk
        end_idx = min(start_idx + max_tokens, total_tokens)
        
        # Extract chunk tokens
        chunk_tokens = token_ids[start_idx:end_idx]
        
        # Decode to text
        chunk_text = encoding.decode(chunk_tokens)
        chunks.append(chunk_text)
        
        # Move to next chunk with overlap
        # If this was the last chunk (reached end), stop
        if end_idx >= total_tokens:
            break
            
        # Otherwise, move forward by (max_tokens - overlap)
        start_idx += max_tokens - overlap_tokens
    
    # Format output based on -out option
    if args.out:
        # Create document format with page_content and empty metadata
        documents = [
            {
                "page_content": chunk,
                "metadata": {}
            }
            for chunk in chunks
        ]
        output = json.dumps(documents, indent=2, ensure_ascii=False)
        Path(args.out).write_text(output, encoding='utf-8')
        print(f"Saved {len(chunks)} chunks to {args.out}")
    else:
        # Original format: just chunk strings
        print(json.dumps(chunks, indent=2))


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

    # --- tokenize ---
    p_tokenize = sub.add_parser("tokenize", help="Tokenize text and return list of token strings, or chunk with overlap")
    group = p_tokenize.add_mutually_exclusive_group(required=True)
    group.add_argument("text", nargs="?", type=str, help="Text to tokenize")
    group.add_argument("-f", "--file", type=str, help="File path to read and tokenize")
    p_tokenize.add_argument("-m", "--max-tokens", type=int, default=None, help="Max tokens per chunk (enables chunking mode)")
    p_tokenize.add_argument("-o", "--overlap", type=int, default=10, help="Token overlap between chunks (default: 10)")
    p_tokenize.add_argument("-out", "--out", type=str, default=None, help="Output file path to save chunks as documents with page_content and empty metadata")
    p_tokenize.set_defaults(func=cmd_tokenize)

    return parser


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)
