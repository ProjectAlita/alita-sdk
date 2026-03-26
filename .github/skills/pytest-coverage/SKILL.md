---
name: "pytest-coverage"
description: "Run branch coverage reports for Python modules using coverage.py with pytest, interpret missing lines and partial branches, and identify gaps to target with new tests"
---

# Pytest Coverage Skill

This skill covers running **branch coverage** with `coverage.py` against any Python source module in the Alita SDK. It tells you which lines and branches are never executed.

---

## Concept: What Coverage Measures

| | Branch Coverage |
|---|---|
| What it measures | Code was **executed** |
| Catches missing `assert` | No |
| Catches wrong assertion | No |
| Speed | ~seconds (single run) |
| Tool | `coverage run --branch` |

Coverage tells you *what was run*. It does **not** tell you whether the tests assert the right things — a line can be executed without any assertion validating its result.

---

## Prerequisites

```bash
source venv/Scripts/activate
pip install coverage pytest
```

> **Do NOT use `pytest --cov=`** — it triggers circular import errors on import of `alita_sdk`. Always use the `coverage run` wrapper instead.

---

## Step 1: Run Coverage + Report in One Command

**Always combine `coverage run` and `coverage report` in a single shell command using `;`** so the report is always generated regardless of test failures. Never run tests separately first to check if they pass — that wastes time and was explicitly flagged as wrong behaviour.

```bash
source venv/Scripts/activate && \
python -m coverage run --branch --source=alita_sdk \
  -m pytest <test_file> -q --no-header --no-cov 2>&1; \
python -m coverage report --include="*/path/to/source.py" -m 2>&1
```

Replace `<test_file>` with the path to the test file, e.g. `tests/runtime/test_my_module.py`.  
Replace `*/path/to/source.py` with a glob matching only the source file(s) under test (e.g. `*/codeparser.py`).

> **Key rules:**
> - Use `;` (not `&&`) between `coverage run` and `coverage report` so the report runs even when tests fail.
> - **Do NOT** run `pytest` separately before coverage — the coverage run IS the test run.
> - **Do NOT** use `pytest --cov=`** — it triggers circular import errors on import of `alita_sdk`.
> - Always pass `--include` to filter the report to only the files you care about.

---

## Step 2: Generate the Report (standalone, if .coverage already exists)

If a `.coverage` data file already exists from a previous run:

```bash
python -m coverage report \
  --include="*/path/to/source1.py,*/path/to/source2.py" -m
```

Use `--include` to filter to only the module(s) you care about. Without it the report covers all of `alita_sdk`.

### Report columns explained

```
Name                          Stmts   Miss Branch BrPart  Cover   Missing
-------------------------------------------------------------------------
alita_sdk/.../security.py      156     71     56      9    50%   84-91, 113-134, ...
```

| Column | Meaning |
|---|---|
| `Stmts` | Total executable statements |
| `Miss` | Statements never executed |
| `Branch` | Total conditional branches |
| `BrPart` | Branches only partially covered (e.g. `if` taken but `else` never, or vice versa) |
| `Cover` | Overall coverage percentage |
| `Missing` | Exact line ranges to target with new tests |

---

## Step 3: Generate an HTML Report (optional)

For a navigable, line-by-line view:

```bash
python -m coverage html --include="*/path/to/source1.py"
# Opens htmlcov/index.html in a browser
```

---

## Step 4: Interpret and Act

### Priority order for new tests

1. **Missing lines (never executed)** — the most urgent gap. There is zero confidence for that code.
2. **Partial branches (`BrPart`)** — one side of a conditional is never tested. Common cause: only the "happy path" is covered.
3. **Lines covered but no assertion validation** — the line runs but no assertion checks the result. Coverage cannot detect this gap; it can only be found by scrutinising test assertions manually.

### Useful coverage thresholds

| Coverage | Recommended action |
|---|---|
| < 60% | Write basic happy-path and error-path tests to reach > 80% before doing anything else |
| 60–80% | Add edge-case and branch-flip tests for `BrPart` lines |
| > 80% | Add targeted assertion tests to validate correctness of covered logic |
| 100% | Coverage is maxed — focus on the quality of assertions in covered code |

---

## Step 5: Re-run After Adding Tests

After writing new tests, re-run the same two commands from Steps 1 and 2 to confirm coverage improved. Repeat until the target threshold is reached.

---

## Common Mistakes

| Mistake | Fix |
|---|---|
| Running pytest separately before coverage to "check if tests pass" | Don't — `coverage run` IS the test run. Combine with `;` and let it run regardless of failures |
| Using `&&` between `coverage run` and `coverage report` | Use `;` so `coverage report` always runs even when tests fail |
| Using `pytest --cov=alita_sdk` | Use `coverage run --branch --source=alita_sdk -m pytest ...` instead |
| Forgetting `--branch` | Without it, only statement coverage is measured; partial branches are invisible |
| Reporting without `--include` | The full `alita_sdk` report is noisy; filter to the specific files under test |
| Treating 100% coverage as "done" | Coverage only proves paths were executed, not that the assertions are correct |

---

## Quick Reference

```bash
# Run coverage
source venv/Scripts/activate
python -m coverage run --branch --source=alita_sdk \
  -m pytest tests/path/to/test_module.py -q --no-header --no-cov

# Terminal report (with missing line numbers)
python -m coverage report --include="*/path/to/my_module.py" -m

# HTML report
python -m coverage html --include="*/path/to/my_module.py"
```
