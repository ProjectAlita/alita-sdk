#!/usr/bin/env python3
"""
Aggregate test results from multiple suite artifacts into a single consolidated
Markdown comment for posting on a GitHub PR.

Scans ``--artifacts-dir`` for ``test-results-*`` subdirectories produced by the
parallel test-execution matrix jobs. Each directory may contain:

  * results.json               – raw test counts
  * results_for_bug_reporter.json – alternate results file (fallback)
  * fix_output.json            – AI fixer analysis
  * fix_milestone.json         – AI milestone / intent analysis
  * bug_report_output.json     – bug-reporter output

The Markdown is written to *stdout* (and optionally to ``--output-file``).

Usage:
    python aggregate_pr_comment.py --artifacts-dir ./artifacts --pr-number 123 --run-url https://…
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> Optional[Dict[str, Any]]:
    """Return parsed JSON or *None* on any error (missing / invalid)."""
    if not path.is_file():
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            print(f"WARNING: {path} is not a JSON object – skipping", file=sys.stderr)
            return None
        return data
    except (json.JSONDecodeError, OSError) as exc:
        print(f"WARNING: failed to read {path}: {exc}", file=sys.stderr)
        return None


def _get(d: Optional[Dict], *keys: str, default: Any = None) -> Any:
    """Safe nested dict access."""
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k, default)
    return cur


# ---------------------------------------------------------------------------
# Data collection
# ---------------------------------------------------------------------------

class SuiteData:
    """Holds all parsed data for one suite."""

    def __init__(self, suite_name: str, artifact_dir: Path):
        self.name = suite_name
        self.dir = artifact_dir

        # Try results.json first, then results_for_bug_reporter.json
        self.results: Optional[Dict] = (
            _load_json(artifact_dir / "results.json")
            or _load_json(artifact_dir / "results_for_bug_reporter.json")
        )
        self.fix_output: Optional[Dict] = _load_json(artifact_dir / "fix_output.json")
        self.fix_milestone: Optional[Dict] = _load_json(artifact_dir / "fix_milestone.json")
        self.bug_report: Optional[Dict] = _load_json(artifact_dir / "bug_report_output.json")

    # -- results helpers --
    @property
    def suite_display(self) -> str:
        return _get(self.results, "suite_name", default=self.name) or self.name

    @property
    def passed(self) -> int:
        return int(_get(self.results, "passed", default=0) or 0)

    @property
    def failed(self) -> int:
        return int(_get(self.results, "failed", default=0) or 0)

    @property
    def errors(self) -> int:
        return int(_get(self.results, "errors", default=0) or 0)

    @property
    def skipped(self) -> int:
        return int(_get(self.results, "skipped", default=0) or 0)

    @property
    def total_ran(self) -> int:
        return self.passed + self.failed + self.errors + self.skipped

    @property
    def is_green(self) -> bool:
        return self.failed == 0 and self.errors == 0

    # -- fix_output helpers --
    @property
    def fixed_count(self) -> int:
        return int(_get(self.fix_output, "summary", "fixed", default=0) or 0)

    @property
    def flaky_count(self) -> int:
        return int(_get(self.fix_output, "summary", "flaky", default=0) or 0)

    @property
    def blocked_count(self) -> int:
        return int(_get(self.fix_output, "summary", "blocked", default=0) or 0)

    @property
    def committed(self) -> bool:
        return _get(self.fix_output, "committed", default=False) is True

    @property
    def fixed_tests(self) -> List[Dict]:
        return _get(self.fix_output, "fixed", default=[]) or []

    @property
    def flaky_tests(self) -> List[Dict]:
        return _get(self.fix_output, "flaky", default=[]) or []

    @property
    def blocked_tests(self) -> List[Dict]:
        return _get(self.fix_output, "blocked", default=[]) or []

    @property
    def commit_details(self) -> Dict:
        return _get(self.fix_output, "commit_details", default={}) or {}

    # -- pr_regression helpers (from fix_output) --
    @property
    def pr_regressions(self) -> List[Dict]:
        return _get(self.fix_output, "pr_regressions", default=[]) or []

    @property
    def pr_regressions_count(self) -> int:
        return int(_get(self.fix_output, "summary", "pr_regressions", default=0) or 0)

    # -- pr_regressions_skipped (from bug_report) --
    @property
    def pr_regressions_skipped(self) -> List[Dict]:
        return _get(self.bug_report, "pr_regressions_skipped", default=[]) or []

    # -- bug_report helpers --
    @property
    def bugs_created(self) -> List[Dict]:
        return _get(self.bug_report, "bugs_created", default=[]) or []

    @property
    def duplicates_skipped(self) -> List[Dict]:
        return _get(self.bug_report, "duplicates_skipped", default=[]) or []

    @property
    def bug_summary(self) -> Dict:
        return _get(self.bug_report, "summary", default={}) or {}

    # -- milestone helpers --
    @property
    def intent_analysis(self) -> List[Dict]:
        return _get(self.fix_milestone, "intent_analysis", default=[]) or []

    @property
    def error_patterns(self) -> List[Dict]:
        return _get(self.fix_milestone, "error_patterns", default=[]) or []

    def ai_verdict(self) -> str:
        """One-liner AI verdict for the summary table."""
        parts: List[str] = []
        if self.fixed_count:
            parts.append(f"{self.fixed_count} fixed")
        if self.flaky_count:
            parts.append(f"{self.flaky_count} flaky")
        if self.blocked_count:
            parts.append(f"{self.blocked_count} blocked")
        if self.pr_regressions_count:
            parts.append(f"{self.pr_regressions_count} PR regression{'s' if self.pr_regressions_count != 1 else ''}")
        return ", ".join(parts) if parts else "—"


def discover_suites(artifacts_dir: Path) -> List[SuiteData]:
    """Find all ``test-results-*`` directories and return parsed suite data."""
    suites: List[SuiteData] = []
    if not artifacts_dir.is_dir():
        return suites
    for child in sorted(artifacts_dir.iterdir()):
        if child.is_dir() and child.name.startswith("test-results-"):
            suite_name = child.name.removeprefix("test-results-")
            suites.append(SuiteData(suite_name, child))
    return suites


# ---------------------------------------------------------------------------
# Markdown generation
# ---------------------------------------------------------------------------

def _status_icon(green: bool) -> str:
    return "✅ PASSED" if green else "❌ FAILED"


def _join_ids(items: List, key: str = "test_ids") -> str:
    """Join test_ids from a list-of-dict entry."""
    ids = items if isinstance(items, list) else []
    return ", ".join(str(i) for i in ids) if ids else "N/A"


def build_markdown(
    suites: List[SuiteData],
    pr_number: Optional[str],
    run_url: Optional[str],
) -> str:
    lines: List[str] = []

    def w(line: str = "") -> None:  # noqa: E731
        lines.append(line)

    # -- header ---
    w("## 🤖 ELITEA SDK Test Results")
    w()
    pr_part = f"**PR #{pr_number}**" if pr_number else ""
    run_part = f"[View full run details]({run_url})" if run_url else ""
    if pr_part or run_part:
        w(f"> {' | '.join(p for p in (pr_part, run_part) if p)}")
        w()

    if not suites:
        w("> **No test results available.** No `test-results-*` artifacts were found.")
        return "\n".join(lines)

    # -- PR regressions banner (if any exist, show early warning) --
    total_pr_regressions = sum(s.pr_regressions_count for s in suites)
    if total_pr_regressions > 0:
        w("> [!CAUTION]")
        w(f"> **{total_pr_regressions} PR regression{'s' if total_pr_regressions != 1 else ''}** "
          "detected — test failures caused by code changes in this PR. See details below.")
        w()

    # -- overall summary table --
    w("### 📊 Overall Summary")
    w()
    w("| Suite | Status | Passed | Failed | Errors | Skipped | AI Verdict |")
    w("|-------|--------|--------|--------|--------|---------|------------|")

    tot_passed = tot_failed = tot_errors = tot_skipped = 0
    any_red = False
    for s in suites:
        tot_passed += s.passed
        tot_failed += s.failed
        tot_errors += s.errors
        tot_skipped += s.skipped
        if not s.is_green:
            any_red = True
        w(
            f"| {s.suite_display} | {_status_icon(s.is_green)} "
            f"| {s.passed} | {s.failed} | {s.errors} | {s.skipped} "
            f"| {s.ai_verdict()} |"
        )
    w(
        f"| **Total** | {_status_icon(not any_red)} "
        f"| **{tot_passed}** | **{tot_failed}** | **{tot_errors}** | **{tot_skipped}** | |"
    )
    w()

    # -- AI-fixed tests (across all suites) --
    all_fixed: List[tuple[str, Dict]] = []
    for s in suites:
        for entry in s.fixed_tests:
            all_fixed.append((s.suite_display, entry))
    if all_fixed:
        w("### ✅ AI-Fixed Tests")
        w()
        w("| Suite | Test(s) | Root Cause | Fix Applied |")
        w("|-------|---------|------------|-------------|")
        for suite_name, entry in all_fixed:
            ids = _join_ids(entry.get("test_ids", []))
            issue = entry.get("issue", "N/A") or "N/A"
            fix = entry.get("fix", "N/A") or "N/A"
            w(f"| {suite_name} | {ids} | {issue} | {fix} |")
        w()

    # -- PR Regressions (bugs introduced by the PR's new code) --
    all_pr_regressions: List[tuple[str, Dict]] = []
    for s in suites:
        for entry in s.pr_regressions:
            all_pr_regressions.append((s.suite_display, entry))
        # Also include regressions that the bug reporter explicitly skipped
        for entry in s.pr_regressions_skipped:
            # Avoid duplicates – only add if test_ids differ from what's already collected
            existing_ids = {
                tuple(sorted(e.get("test_ids", [])))
                for sn, e in all_pr_regressions
                if sn == s.suite_display
            }
            entry_ids = tuple(sorted(entry.get("test_ids", [])))
            if entry_ids not in existing_ids:
                all_pr_regressions.append((s.suite_display, entry))
    if all_pr_regressions:
        w("### ⚠️ PR Regressions — Bugs Introduced by This PR")
        w()
        w("> [!CAUTION]")
        w("> The following test failures are caused by **code changes in this PR**, ")
        w("> not pre-existing SDK bugs. These were **not** reported to the bug board.")
        w("> Please fix the issues below before merging.")
        w()
        for suite_name, entry in all_pr_regressions:
            ids = _join_ids(entry.get("test_ids", []))
            bug_desc = entry.get("bug_description", "N/A") or entry.get("description", "N/A") or "N/A"
            component = entry.get("sdk_component", "N/A") or entry.get("affected_component", "N/A") or "N/A"
            methods = ", ".join(entry.get("affected_methods", []) or entry.get("pr_changed_methods", []) or []) or "N/A"
            recommendation = entry.get("recommendation", "N/A") or "N/A"
            file_changed = entry.get("pr_changed_this_file", "N/A") or "N/A"
            method_changed = entry.get("pr_changed_this_method", "N/A") or "N/A"
            w(f"<details>")
            w(f"<summary><b>[{suite_name}] {ids}</b> — {bug_desc}</summary>")
            w()
            w("| Field | Detail |")
            w("|-------|--------|")
            w(f"| Bug Description | {bug_desc} |")
            w(f"| SDK Component | {component} |")
            w(f"| Affected Methods | {methods} |")
            w(f"| Changed File | {file_changed} |")
            w(f"| Changed Method | {method_changed} |")
            w(f"| Recommendation | {recommendation} |")
            w()
            w("</details>")
            w()

    # -- Flaky tests --
    all_flaky: List[tuple[str, Dict]] = []
    for s in suites:
        for entry in s.flaky_tests:
            all_flaky.append((s.suite_display, entry))
    if all_flaky:
        w("### ⚠️ Flaky Tests")
        w()
        w("> [!WARNING]")
        w("> The following tests failed initially but passed on rerun.")
        w()
        w("| Suite | Test(s) | Reason |")
        w("|-------|---------|--------|")
        for suite_name, entry in all_flaky:
            ids = _join_ids(entry.get("test_ids", []))
            reason = entry.get("reason", "N/A") or "N/A"
            w(f"| {suite_name} | {ids} | {reason} |")
        w()

    # -- Blocked tests (SDK bugs) --
    all_blocked: List[tuple[str, Dict]] = []
    for s in suites:
        for entry in s.blocked_tests:
            all_blocked.append((s.suite_display, entry))
    if all_blocked:
        w("### ❌ Blocked Tests — SDK Bugs")
        w()
        w("> [!IMPORTANT]")
        w("> These tests were **not patched** because the failures are caused by SDK "
          "code defects, not test logic errors.")
        w()
        for suite_name, entry in all_blocked:
            ids = _join_ids(entry.get("test_ids", []))
            bug_desc = entry.get("bug_description", "N/A") or "N/A"
            expected = entry.get("expected_behavior", "N/A") or "N/A"
            actual = entry.get("actual_behavior", "N/A") or "N/A"
            component = entry.get("sdk_component", "N/A") or "N/A"
            methods = ", ".join(entry.get("affected_methods", []) or []) or "N/A"
            location = entry.get("error_location", "N/A") or "N/A"
            w(f"<details>")
            w(f"<summary><b>[{suite_name}] {ids}</b> — {bug_desc}</summary>")
            w()
            w("| Field | Detail |")
            w("|-------|--------|")
            w(f"| Bug Description | {bug_desc} |")
            w(f"| Expected Behavior | {expected} |")
            w(f"| Actual Behavior | {actual} |")
            w(f"| SDK Component | {component} |")
            w(f"| Affected Methods | {methods} |")
            w(f"| Error Location | {location} |")
            w()
            w("</details>")
            w()

    # -- Bug reports --
    all_bugs_created: List[tuple[str, Dict]] = []
    all_dupes_skipped: List[tuple[str, Dict]] = []
    for s in suites:
        for b in s.bugs_created:
            all_bugs_created.append((s.suite_display, b))
        for d in s.duplicates_skipped:
            all_dupes_skipped.append((s.suite_display, d))
    if all_bugs_created or all_dupes_skipped:
        w("### 🐛 Bug Reports")
        w()
        if all_bugs_created:
            w("**New bugs created:**")
            w()
            w("| Suite | Title | Test(s) | Component | Labels |")
            w("|-------|-------|---------|-----------|--------|")
            for suite_name, b in all_bugs_created:
                title = b.get("title", "N/A") or "N/A"
                url = b.get("issue_url", "")
                title_md = f"[{title}]({url})" if url else title
                ids = _join_ids(b.get("test_ids", []))
                comp = b.get("affected_component", "N/A") or "N/A"
                labels = ", ".join(b.get("labels", []) or []) or "—"
                w(f"| {suite_name} | {title_md} | {ids} | {comp} | {labels} |")
            w()
        if all_dupes_skipped:
            w("**Existing bugs matched (deduplicated):**")
            w()
            for suite_name, d in all_dupes_skipped:
                ids = _join_ids(d.get("test_ids", []))
                existing_title = d.get("existing_issue_title", "N/A") or "N/A"
                existing_url = d.get("existing_issue_url", "")
                reason = d.get("similarity_reason", "N/A") or "N/A"
                link = f"[{existing_title}]({existing_url})" if existing_url else existing_title
                w(f"- **[{suite_name}] Tests:** {ids}")
                w(f"  - **Similar to:** {link}")
                w(f"  - **Reason:** {reason}")
            w()

    # -- Commit info (any suite that committed fixes) --
    committed_suites = [s for s in suites if s.committed]
    if committed_suites:
        w("### 🔧 AI Commits")
        w()
        w("> [!TIP]")
        w("> The AI fixer committed code changes to fix failing tests.")
        w()
        w("| Suite | Branch | Files Changed | PR |")
        w("|-------|--------|---------------|----|")
        for s in committed_suites:
            cd = s.commit_details
            branch = cd.get("branch", "N/A") or "N/A"
            files = cd.get("files_count", 0)
            pr = cd.get("pr_number")
            pr_display = f"#{pr}" if pr else "—"
            w(f"| {s.suite_display} | `{branch}` | {files} | {pr_display} |")
        w()

    # -- Per-suite details (collapsible) --
    w("<details>")
    w("<summary>📋 Per-Suite Details</summary>")
    w()
    for s in suites:
        w(f"#### {s.suite_display}")
        w()
        if s.results is None:
            w("> ⚠️ No results file found for this suite.")
            w()
            continue

        w(f"- **Status:** {_status_icon(s.is_green)}")
        w(f"- **Passed:** {s.passed} | **Failed:** {s.failed} | "
          f"**Errors:** {s.errors} | **Skipped:** {s.skipped}")

        # Individual test list from results.tests[]
        tests_list = _get(s.results, "tests", default=[]) or []
        if tests_list:
            w()
            w("| Test | Status | Duration |")
            w("|------|--------|----------|")
            for t in tests_list:
                tid = t.get("test_id") or t.get("name") or "?"
                status = t.get("status", "unknown")
                icon = {"passed": "✅", "failed": "❌", "error": "💥", "skipped": "⏭️"}.get(
                    status.lower(), "❓"
                )
                dur = t.get("duration") or t.get("elapsed_time") or "—"
                if isinstance(dur, (int, float)):
                    dur = f"{dur:.1f}s"
                w(f"| {tid} | {icon} {status} | {dur} |")

        # Intent analysis from milestone
        intent = s.intent_analysis
        if intent:
            w()
            w("<details>")
            w(f"<summary>🔍 Intent Analysis — {len(intent)} tests classified</summary>")
            w()
            w("| Test | Type | Classification | Reasoning |")
            w("|------|------|----------------|-----------|")
            for ia in intent:
                tid = ia.get("test_id", "N/A")
                pos_neg = ia.get("positive_or_negative", "N/A")
                cls = ia.get("classification", "N/A")
                if cls == "pr_regression":
                    cls_icon = "⚠️ PR Regression"
                elif cls == "sdk_bug":
                    cls_icon = "🐛 SDK Bug"
                else:
                    cls_icon = "🔧 Test Issue"
                reasoning = ia.get("reasoning", "N/A") or "N/A"
                w(f"| {tid} | {pos_neg} | {cls_icon} | {reasoning} |")
            w()
            w("</details>")

        # Error patterns from milestone
        patterns = s.error_patterns
        if patterns:
            w()
            w("<details>")
            w(f"<summary>📌 Error Patterns — {len(patterns)} patterns</summary>")
            w()
            w("| Pattern | Tests | Category |")
            w("|---------|-------|----------|")
            for ep in patterns:
                cause = ep.get("root_cause", "Unknown") or "Unknown"
                ep_ids = ", ".join(ep.get("test_ids", []) or []) or "—"
                cat = ep.get("category", "unknown")
                if cat == "pr_regression":
                    cat_icon = "⚠️ PR Regression"
                elif cat == "sdk_bug":
                    cat_icon = "🐛 SDK Bug"
                else:
                    cat_icon = "🔧 Test Issue"
                w(f"| {cause} | {ep_ids} | {cat_icon} |")
            w()
            w("</details>")

        w()
        w("---")
        w()

    w("</details>")
    w()

    # -- footer --
    w("---")
    w("*Generated by ELITEA SDK Test Pipeline*")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Aggregate per-suite test artifacts into a consolidated PR comment (Markdown).",
    )
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=Path("./artifacts"),
        help="Directory containing test-results-* subdirectories (default: ./artifacts)",
    )
    parser.add_argument(
        "--pr-number",
        default=None,
        help="PR number to reference in the comment header.",
    )
    parser.add_argument(
        "--run-url",
        default=None,
        help="URL of the workflow run for the 'View full run details' link.",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=None,
        help="Optionally write the Markdown to this file in addition to stdout.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    args = parse_args(argv)

    suites = discover_suites(args.artifacts_dir)
    if not suites:
        print(
            f"WARNING: no test-results-* directories found under {args.artifacts_dir}",
            file=sys.stderr,
        )

    md = build_markdown(suites, pr_number=args.pr_number, run_url=args.run_url)

    # Always write to stdout
    sys.stdout.write(md)
    if not md.endswith("\n"):
        sys.stdout.write("\n")

    # Optionally write to file
    if args.output_file:
        args.output_file.parent.mkdir(parents=True, exist_ok=True)
        args.output_file.write_text(md, encoding="utf-8")
        print(f"Wrote {len(md)} bytes to {args.output_file}", file=sys.stderr)


if __name__ == "__main__":
    main()
