---
name: "mutation-testing"
description: "Set up, run, and interpret cosmic-ray mutation tests against Python source modules using Docker workers for parallel execution"
---

# Mutation Testing Skill

This skill covers setting up and running mutation testing with **cosmic-ray** against any Python source module in the Alita SDK, using Docker workers for parallel execution. It captures the exact workflow, pitfalls, and fixes discovered during the initial setup.

---

## When to Use This Skill

- Evaluating whether a test suite truly validates logic (not just executes code)
- After achieving high branch coverage but wanting stronger confidence
- Before declaring a test suite "complete" for a security-critical module
- When asked to "check mutation testing", "run mutations", or "verify test quality"

---

## Concept: Coverage vs Mutations

| | Branch Coverage | Mutation Testing |
|---|---|---|
| What it measures | Code was **executed** | Logic was **verified** |
| Catches missing `assert` | No | Yes |
| Catches wrong assertion | No | Yes |
| Speed | ~seconds (single run) | Minutes (one run per mutation) |
| Tool | `coverage run --branch` | `cosmic-ray` |

**Use coverage first** (fast, find unexecuted paths), **then mutations** (find weak assertions in covered paths).

---

## Prerequisites

### Platform Check
- `mutmut` does **not** work on Windows natively — use `cosmic-ray` instead
- `cosmic-ray` v8.4.4+ works on Windows as the **coordinator**, but workers must run in Linux Docker containers

### Install
```bash
source venv/Scripts/activate
pip install cosmic-ray coverage
```

### One-Time Windows Fix (REQUIRED before first run)

`cosmic-ray`'s HTTP distributor serializes module paths with `str(mutation.module_path)`. On Windows this produces `WindowsPath` backslashes (`alita_sdk\runtime\...\module.py`). Linux Docker workers receive that string, wrap it in `Path()`, and fail with `FileNotFoundError` because on Linux `\` is not a path separator.

**Fix**: patch one line in the installed venv package — do this once after installing cosmic-ray:

```bash
# Find the file
python -c "import cosmic_ray.distribution.http as m; print(m.__file__)"
```

Open the file shown and change:
```python
"module_path": str(mutation.module_path),
```
to:
```python
"module_path": str(mutation.module_path).replace("\\", "/"),
```

> This is a permanent fix for your local venv. If you recreate the venv, reapply it.
> Also note: patching the SQLite database paths is **not sufficient** — `work_db.py` re-wraps every path through `pathlib.Path()` on every read, restoring the `WindowsPath` backslashes before `send_request()` sees them.

---

## Step 1: Quick Smoke Check (Branch Coverage)

Run this first — it finishes in one test-suite duration and exposes all unexecuted paths.

```bash
source venv/Scripts/activate
python -m coverage run --branch --source=alita_sdk \
  -m pytest <test_file> -q --no-header --no-cov
python -m coverage report \
  --include="*/path/to/source1.py,*/path/to/source2.py" -m
```

> **Do NOT use `pytest --cov=`** — it triggers circular import errors on import of alita_sdk. Always use `coverage run` wrapper instead.

### Read the report

```
Name                          Stmts   Miss Branch BrPart  Cover   Missing
-------------------------------------------------------------------------
alita_sdk/.../security.py      156     71     56      9    50%   84-91, 113-134, ...
```

- **Miss**: lines never executed
- **BrPart**: branches partially covered (e.g. only `if` taken, never `else`)
- **Missing**: exact lines/ranges to target with new tests

---

## Step 2: Mutation Testing Setup

### 2a. Dockerfile for Workers

Create `Dockerfile.mutation-worker` in the project root:

```dockerfile
FROM ghcr.io/projectalita/alita-sdk:pyodide

WORKDIR /app
RUN pip install --no-cache-dir cosmic-ray

COPY alita_sdk/ ./alita_sdk/
COPY tests/ ./tests/
COPY pyproject.toml ./

EXPOSE 8080
CMD ["cosmic-ray", "--verbosity", "INFO", "http-worker", "--port", "8080"]
```

> Each worker container has its **own independent copy** of the source code. This prevents file-locking conflicts when multiple workers mutate files simultaneously.

### 2b. Docker Compose for Workers

Create `docker-compose.mutation.yml`:

```yaml
services:
  mutation-worker-1:
    build:
      context: .
      dockerfile: Dockerfile.mutation-worker
    container_name: cr-worker-1
    ports:
      - "8001:8080"

  mutation-worker-2:
    build:
      context: .
      dockerfile: Dockerfile.mutation-worker
    container_name: cr-worker-2
    ports:
      - "8002:8080"

  mutation-worker-3:
    build:
      context: .
      dockerfile: Dockerfile.mutation-worker
    container_name: cr-worker-3
    ports:
      - "8003:8080"
```

### 2c. cosmic-ray Config (one per source module)

Create `cosmic-ray-<module>.toml`:

```toml
[cosmic-ray]
module-path = "alita_sdk/runtime/middleware/sensitive_tool_guard.py"
timeout = 90.0
excluded-modules = []

# test-command runs on the Windows coordinator host (not inside Docker workers)
test-command = "python -m pytest tests/runtime/test_sensitive_tool_masking.py -x -q --no-header --tb=no"

[cosmic-ray.distributor]
name = "http"

[cosmic-ray.distributor.http]
worker-urls = [
    "http://localhost:8001",
    "http://localhost:8002",
    "http://localhost:8003",
]
```

> **Worker URLs use `localhost` (not container names).** The coordinator runs on the Windows host and reaches the Docker workers via their published ports (`8001-8003`). This works once the `http.py` patch (see Prerequisites) is applied — without it, the coordinator sends backslash paths that Linux workers can't resolve.

> **Do NOT put operators in `[cosmic-ray.operators]`** — no-arg operators must not be listed at all. Listing them (even with `[]` or `[{}]`) raises `TypeError: Arguments provided for operator X which accepts no arguments`. The section only exists for parameterized operators.

---

## Step 3: Build and Start Workers

```bash
docker compose -f docker-compose.mutation.yml up --build -d
```

Verify workers respond:
```bash
curl http://localhost:8001  # expects: 405 Method Not Allowed
curl http://localhost:8002
curl http://localhost:8003
```

`405` = worker is up and listening (it only accepts POST, not GET).

---

## Step 4: Initialize Session and Prune Operators

```bash
source venv/Scripts/activate

# Initialize (seeds ALL operators)
cosmic-ray init cosmic-ray-<module>.toml cr-<module>.sqlite
```

### Prune to logic operators only (faster, more meaningful)

By default cosmic-ray seeds hundreds of operators (arithmetic, string, etc.)
Run this Python snippet to keep only the boolean/comparison operators that matter for logic coverage:

```python
import sqlite3

KEEP = {
    "core/AddNot",
    "core/ReplaceTrueWithFalse",
    "core/ReplaceFalseWithTrue",
    "core/ReplaceAndWithOr",
    "core/ReplaceOrWithAnd",
    "core/ReplaceComparisonOperator_Eq_NotEq",
    "core/ReplaceComparisonOperator_NotEq_Eq",
    "core/ReplaceComparisonOperator_Is_IsNot",
    "core/ReplaceComparisonOperator_IsNot_Is",
}

conn = sqlite3.connect("cr-security.sqlite")
conn.execute(f"""
    DELETE FROM work_items WHERE job_id IN (
        SELECT job_id FROM mutation_specs WHERE operator_name NOT IN ({",".join(f"'{o}'" for o in KEEP)})
    )
""")
conn.execute(f"""
    DELETE FROM mutation_specs WHERE operator_name NOT IN ({",".join(f"'{o}'" for o in KEEP)})
""")
conn.commit()
print(conn.execute("SELECT COUNT(*) FROM work_items").fetchone()[0], "mutations remaining")
conn.close()
```

---

## Step 5: Run Mutations (Windows host coordinator)

With the `http.py` patch applied (see Prerequisites), run the coordinator directly on the Windows host. It sends forward-slash paths over HTTP, so Linux Docker workers resolve them correctly.

```bash
source venv/Scripts/activate

# Baseline check — verify tests pass before mutating
cosmic-ray --verbosity=ERROR baseline cosmic-ray-<module>.toml

# Run all mutations (blocks until complete; ~1–3 min per 100 mutations with 3 workers)
cosmic-ray exec cosmic-ray-<module>.toml cr-<module>.sqlite
```

> Workers run in Docker on `localhost:8001-8003`. The coordinator is on the Windows host. This works because the http.py patch converts `WindowsPath` backslashes to forward slashes before sending JSON to workers.

> **Do NOT use the Docker coordinator approach** (`docker run ... cosmic-ray exec ...`) unless the http.py patch is unavailable. The patch is simpler and eliminates the need for network name discovery, volume mounts, and container name resolution.

---

## Step 6: Check Progress

```python
import sqlite3
conn = sqlite3.connect("cr-security.sqlite")
total = conn.execute("SELECT COUNT(*) FROM work_items").fetchone()[0]
done  = conn.execute("SELECT COUNT(*) FROM work_results").fetchone()[0]
outcomes = conn.execute(
    "SELECT worker_outcome, test_outcome, COUNT(*) FROM work_results GROUP BY worker_outcome, test_outcome"
).fetchall()
conn.close()
print(f"{done}/{total}")
for r in outcomes: print(f"  {r[0]}/{r[1]}: {r[2]}")
```

Expected healthy output:
```
52/52
  NORMAL/KILLED: 52
```

---

## Step 7: View Results

```bash
source venv/Scripts/activate

# Terminal summary
cr-report cr-security.sqlite --show-pending

# Full HTML report
cr-html cr-security.sqlite > report-security.html
```

### Interpret the summary line

```
total jobs: 52
complete: 52 (100.00%)
surviving mutants: 3 (5.77%)   ← gaps to investigate
```

- **Killed** — test suite caught the mutation ✓
- **Survived** — tests passed even with broken logic ✗ (write more tests)
- **Incompetent** — worker crashed before tests ran (see Troubleshooting)

---

## Interpreting Results vs Coverage

| Coverage | Mutation score | Meaning |
|---|---|---|
| Low (< 60%) | Any | Tests don't reach the code — write coverage tests first |
| High (> 80%) | High (many survived) | Tests run the code but don't assert correctly |
| High (> 80%) | Low (few survived) | Tests are strong for covered code |
| Any | 100% killed | Covered code is well-tested — focus on uncovered branches |

---

## Troubleshooting

### `TypeError: Arguments provided for operator X which accepts no arguments`
Caused by listing no-arg operators in `[cosmic-ray.operators]` with any value (even `[]` or `[{}]`).
**Fix**: Remove the `[cosmic-ray.operators]` section entirely. No-arg operators run automatically.

### `EXCEPTION/INCOMPETENT: N` — all mutations fail with `FileNotFoundError: alita_sdk\runtime\...\module.py`

This is the Windows backslash path bug. See **Prerequisites → One-Time Windows Fix** for the root cause and the one-line patch to apply to `venv/Lib/site-packages/cosmic_ray/distribution/http.py`.

Quick recap: `str(mutation.module_path)` on Windows produces backslash paths; Linux workers receive them via HTTP and can't resolve them. Patch the line to `.replace("\\", "/")`.

> Patching SQLite paths is **not sufficient** — `work_db.py` re-wraps every path via `pathlib.Path()` on every read, restoring backslashes before the HTTP layer sees them.

### `405 Method Not Allowed` from `curl http://localhost:8001`
This is **correct** — cosmic-ray HTTP workers only accept POST requests. The worker is healthy.

### Workers show 0 results after `exec`
The `work_results` table is empty. Check:
1. Are containers running? `docker ps`
2. Can the coordinator reach workers? `curl http://localhost:8001` → expect `405`
3. Is the `http.py` patch applied? If not, all mutations will be `INCOMPETENT` (not 0 results, but useful to check).

---

## Full End-to-End Command Reference (Windows)

> **One-time setup required**: Apply the `http.py` patch from the Prerequisites section before your first run.

```bash
# 1. Start Docker workers
docker compose -f docker-compose.mutation.yml up -d
# Verify: curl http://localhost:8001  → 405 = healthy
# Verify: curl http://localhost:8002  → 405 = healthy
# Verify: curl http://localhost:8003  → 405 = healthy

# 2. Smoke check (branch coverage — fast sanity check)
source venv/Scripts/activate
python -m coverage run --branch --source=alita_sdk \
  -m pytest tests/runtime/test_my_module.py -q --no-header --no-cov
python -m coverage report --include="*/path/to/my_module.py" -m

# 3. Initialize mutation session
cosmic-ray init cosmic-ray-my-module.toml cr-my-module.sqlite

# 4. Prune to logic operators only (run prune script from Step 4)

# 5. Baseline — verify tests pass before mutating
cosmic-ray --verbosity=ERROR baseline cosmic-ray-my-module.toml

# 6. Execute mutations (coordinator runs on Windows host)
cosmic-ray exec cosmic-ray-my-module.toml cr-my-module.sqlite

# 7. Report
cr-report cr-my-module.sqlite --show-pending 2>&1 | tail -4
cr-html   cr-my-module.sqlite > report-my-module.html

# 8. Shut down workers
docker compose -f docker-compose.mutation.yml down
```

> **Why Docker workers?** Each worker container has an independent copy of the source code. When cosmic-ray mutates a file, it writes the mutant directly to disk — if multiple workers shared a single copy, they would overwrite each other's mutations. Docker containers provide isolated `/app` directories so workers can mutate concurrently without conflicts.

> **Why NOT `cr-http-workers`** (the official parallel wrapper)? It clones the git repo per worker using a `file://` URL. On Windows, Git Bash percent-encodes backslashes in the path (`%5C`), which breaks the clone. Docker workers are the simpler and reliable alternative.

---

## Alternative: mutmut (Coverage-Guided, Docker)

mutmut provides PIT-like coverage-guided test selection — it only runs tests that cover the mutated line, ordered by speed. This is fundamentally different from cosmic-ray which runs the full test command for every mutation.

> **Use mutmut v2** (`pip install "mutmut<3"`). mutmut v3 has a `PermissionError` on `/proc` when running in Docker containers as PID 1. v2 is stable and supports all CLI flags documented below.

### Quick Start

```bash
# Build (one-time)
docker build -f Dockerfile.mutmut -t alita-mutmut .

# Run (results volume-mounted to host)
docker run --rm -v "$(pwd)/mutmut-results:/app/mutmut-results" alita-mutmut

# View results
cat mutmut-results/mutmut-results.txt
```

### Comparison: cosmic-ray vs mutmut

| Aspect | cosmic-ray | mutmut |
|---|---|---|
| Architecture | 3 Docker workers + coordinator | Single container |
| Test selection | Runs full pytest command per mutation | Coverage-guided (only relevant tests) |
| Operator control | Manual pruning via SQLite | All operators, no pruning needed |
| Windows support | Needs path patches + Docker coordinator | Runs in Docker only |
| Resumable | No (re-init required) | Yes (remembers completed work) |
| Config | Separate TOML + SQLite | `[tool.mutmut]` in pyproject.toml |
| Output | SQLite DB + HTML via `cr-html` | HTML report + text summary |
| Setup complexity | High (Dockerfile, compose, patches) | Low (1 Dockerfile, 1 script) |

### When to use which

- **cosmic-ray**: When you need fine-grained operator control (e.g., only boolean/comparison mutations) or want to parallelize across multiple workers for large modules
- **mutmut**: For most cases — simpler setup, smarter test selection, resumable runs
