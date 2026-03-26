---
name: "mutation-testing"
description: "Set up, run, and interpret cosmic-ray mutation tests against Python source modules using Docker workers for parallel execution"
---

# Mutation Testing Skill

This skill covers setting up and running mutation testing with **cosmic-ray** against any Python source module in the Alita SDK, using Docker workers for parallel execution. It captures the exact workflow, pitfalls, and fixes discovered during the initial setup.

---

## CRITICAL: What This Skill Does and Does NOT Do

**This skill's purpose is to:**
1. Run mutation tests
2. Report surviving mutants and bugs surfaced by failing tests
3. **Suggest** fixes with a clear description of the change needed

**This skill must NEVER:**
- Modify source code (the module under test) without explicit developer confirmation
- "Fix" failing tests by changing the source to match test assertions
- Apply any code change to resolve a test failure without being asked

**When tests fail during the baseline run:**
- Document each failure with its root cause
- Describe the suggested fix
- **Stop and ask the developer** whether to apply each fix before proceeding

> Example correct response: "Tests X, Y, Z fail. They are BUG DETECTOR tests exposing [description]. Suggested fix: [change]. Do you want me to apply it?"

---

## When to Use This Skill

- Evaluating whether a test suite truly validates logic (not just executes code)
- When you want to verify that tests don't just execute code but actually validate logic
- Before declaring a test suite "complete" for a security-critical module
- When asked to "check mutation testing", "run mutations", or "verify test quality"

---

## Concept: What Mutation Testing Measures

| | Mutation Testing |
|---|---|
| What it measures | Logic was **verified** |
| Catches missing `assert` | Yes |
| Catches wrong assertion | Yes |
| Speed | Minutes (one run per mutation) |
| Tool | `cosmic-ray` |

Mutation testing answers: *"If I break a line of logic, do the tests catch it?"* It goes beyond checking if code was executed — it verifies that the tests actually assert something meaningful.

---

## Prerequisites

### Platform Check
- `cosmic-ray` v8.4.4+ works on Windows as the **coordinator**, but workers must run in Linux Docker containers

### Install
```bash
source venv/Scripts/activate
pip install cosmic-ray
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

## Step 1: Mutation Testing Setup

### 1a. Dockerfile for Workers

See `Dockerfile.mutation-worker` in the project root. Each worker container has its **own independent copy** of the source code — this prevents file-locking conflicts when multiple workers mutate files simultaneously.

### 1b. Docker Compose for Workers

See `docker-compose.mutation.yml` in the project root. It defines three workers exposed on `localhost:8001-8003`.

### 1c. cosmic-ray Config (one per source module)

Create `cosmic-ray-<module>.toml` (not committed to git — create per module as needed):

```toml
[cosmic-ray]
module-path = "alita_sdk/path/to/module.py"
timeout = 90.0
excluded-modules = []

# test-command runs on the Windows coordinator host (not inside Docker workers)
test-command = "python -m pytest tests/path/to/test_module.py -x -q --no-header --tb=no"

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

## Step 2: Build and Start Workers

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

## Step 3: Initialize Session and Prune Operators

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

## Step 4: Run Mutations (Windows host coordinator)

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

## Step 5: Check Progress

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

## Step 6: View Results

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

## Interpreting Results

| Mutation score | Meaning |
|---|---|
| Many survived | Tests run the code but don’t assert correctly |
| Few survived | Tests are strong for covered code |
| 100% killed | Covered code is well-tested |

---

## Survivor Analysis Protocol

**When a mutation survives, NEVER write a test purely to kill it.**

A surviving mutation is a question: *"Does this logic change matter?"* Your job is to answer that question — not just make it go away.

### Required workflow for each survivor

1. **Identify what changed** — what logic was mutated (e.g. `False` → `True`, `>` → `>=`, `and` → `or`).
2. **Understand the intent** — read the docstring, function name, and surrounding code. What *should* happen here?
3. **Decide:**

| Situation | Action |
|---|---|
| Intent is clear, current code is **correct** | Write a test asserting the correct behaviour (test passes, mutation is now killed legitimately) |
| Intent is clear, current code is **wrong** | Write a test asserting the correct behaviour (test **fails** on purpose — file a bug report, do NOT "fix" the test to match the wrong code) |
| Intent is **unclear** | Do NOT write a test. Report the ambiguity to the developer and wait for a decision. |

### The mutation-score chasing trap

Writing tests that assert the *current broken behaviour* purely to boost kill rate is **worse than leaving mutations alive**:

- It encodes bugs as expected behaviour.
- It gives false confidence ("96% kill rate!") while actively hiding defects.
- It makes genuine bug fixes break the test suite, making tests adversarial to developers.

### Red flags — stop and report if you catch yourself:

- [ ] Writing a test and immediately checking whether it kills the surviving mutation (score-first thinking).
- [ ] Asserting a value you are not certain is the *intended correct* value.
- [ ] Changing a test assertion from "what should be true" to "what currently happens".
- [ ] Getting a higher kill rate but the test feels semantically wrong.

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

# 2. Initialize mutation session
source venv/Scripts/activate
cosmic-ray init cosmic-ray-my-module.toml cr-my-module.sqlite

# 3. Prune to logic operators only (run prune script from Step 3)

# 4. Baseline — verify tests pass before mutating
cosmic-ray --verbosity=ERROR baseline cosmic-ray-my-module.toml

# 5. Execute mutations (coordinator runs on Windows host)
cosmic-ray exec cosmic-ray-my-module.toml cr-my-module.sqlite

# 6. Report
cr-report cr-my-module.sqlite --show-pending 2>&1 | tail -4
cr-html   cr-my-module.sqlite > report-my-module.html

# 7. Shut down workers
docker compose -f docker-compose.mutation.yml down
```

> **Why Docker workers?** Each worker container has an independent copy of the source code. When cosmic-ray mutates a file, it writes the mutant directly to disk — if multiple workers shared a single copy, they would overwrite each other's mutations. Docker containers provide isolated `/app` directories so workers can mutate concurrently without conflicts.

> **Why NOT `cr-http-workers`** (the official parallel wrapper)? It clones the git repo per worker using a `file://` URL. On Windows, Git Bash percent-encodes backslashes in the path (`%5C`), which breaks the clone. Docker workers are the simpler and reliable alternative.
