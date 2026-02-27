#!/usr/bin/env python3
"""
slim_results.py
---------------
Strips a test-pipeline results.json down to the fields that matter for
failure diagnosis and test-fixer analysis.

Usage:
    python scripts/slim_results.py <input_results.json> [output_slim.json]

If output path is omitted, writes <input>_slim.json next to the input file.
"""

import json
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Field filters
# ---------------------------------------------------------------------------

def slim_tool_call(tc: dict) -> dict:
    """Keep only the fields needed to understand what a tool did and whether
    it succeeded."""
    return {
        "tool_name":   tc.get("tool_name"),
        "tool_inputs": tc.get("tool_inputs"),
        "tool_output": tc.get("tool_output"),
        "finish_reason": tc.get("finish_reason"),
        "error":       tc.get("error"),
    }


def slim_thinking_step(step: dict) -> dict:
    """Keep the LLM reasoning text and its finish reason (detects truncation)."""
    finish_reason = None
    gi = step.get("generation_info")
    if isinstance(gi, dict):
        finish_reason = gi.get("finish_reason")

    return {
        "text":         step.get("text"),
        "finish_reason": finish_reason,
    }


def slim_output(output: dict) -> dict:
    """Strip output to the diagnostically relevant subset."""
    if output is None:
        return None

    # tool_calls_dict: dict keyed by UUID → slim each entry
    raw_tcd = output.get("tool_calls_dict") or {}
    slimmed_tcd = {k: slim_tool_call(v) for k, v in raw_tcd.items()}

    # thinking_steps: list
    raw_ts = output.get("thinking_steps") or []
    slimmed_ts = [slim_thinking_step(s) for s in raw_ts]

    return {
        "result":                      output.get("result"),
        "error":                       output.get("error"),
        "chat_history_tokens_input":   output.get("chat_history_tokens_input"),
        "llm_response_tokens_output":  output.get("llm_response_tokens_output"),
        "thinking_steps":              slimmed_ts or None,
        "tool_calls_dict":             slimmed_tcd or None,
    }


def slim_result(r: dict) -> dict:
    """Reduce a single test result entry to failure-relevant fields only."""
    return {
        "pipeline_name": r.get("pipeline_name"),
        "test_passed":   r.get("test_passed"),
        "success":       r.get("success"),   # execution success (pipeline ran)
        "error":         r.get("error"),     # top-level crash (no output at all)
        "output":        slim_output(r.get("output")),
    }


def slim_results(data: dict) -> dict:
    """Remap the full results payload, keeping only failed/errored tests."""
    results = data.get("results") or []

    # Keep only tests that did not pass:
    #   test_passed is False  → assertion failure
    #   test_passed is None   → pipeline crashed (success=False, output=None)
    failing = [
        slim_result(r) for r in results
        if r.get("test_passed") is not True
    ]

    return {
        "suite_name":    data.get("suite_name"),
        "total":         data.get("total"),
        "passed":        data.get("passed"),
        "failed":        data.get("failed"),
        "errors":        data.get("errors"),
        "skipped":       data.get("skipped"),
        "failing_count": len(failing),
        "results":       failing,
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    input_path = Path(sys.argv[1])
    if not input_path.exists():
        print(f"ERROR: file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    if len(sys.argv) >= 3:
        output_path = Path(sys.argv[2])
    else:
        output_path = input_path.with_name(input_path.stem + "_errors_only.json")

    with input_path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)

    slimmed = slim_results(data)

    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(slimmed, fh, indent=2, ensure_ascii=False)

    original_size = input_path.stat().st_size
    slimmed_size  = output_path.stat().st_size
    reduction     = 100 * (1 - slimmed_size / original_size)

    print(f"Written: {output_path}")
    print(f"Size:    {original_size:,} → {slimmed_size:,} bytes  ({reduction:.0f}% reduction)")


if __name__ == "__main__":
    main()
