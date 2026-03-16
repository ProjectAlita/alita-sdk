---
name: "document-loader-tests"
description: "Run, filter, and diagnose document loader pytest tests"
---

# Document Loader Tests Skill

This skill covers running document loader unit tests, filtering by tag for impact analysis, managing baselines, and diagnosing failures.

All test suites in `tests/runtime/langchain/` follow the same pattern — if new test suites are added, the same commands, structure, and conventions described here apply to them.

## When to Use This Skill

- Running the full or partial test suite for any loader or component under `tests/runtime/langchain/`
- Re-running only tests related to a specific change (impact analysis via tags)
- Updating or regenerating baseline output files
- Diagnosing and understanding test failures
- Adding new test suites following the same structure

---

## Repeatable Test Suite Structure

Every test suite under `tests/runtime/langchain/<component>/` follows this layout:

```
tests/runtime/langchain/<component>/
  test_<subject>.py          # pytest module (parametrized via collect_loader_test_params)
  test_data/
    <SubjectClass>/
      files/                 # actual test data files (inputs to the loader/component)
      input/                 # JSON test definitions: file_path, configs[], tags[]
      output/                # committed baseline JSONs (expected output)
    scripts/
      loader_test_runner.py  # execution engine (LoaderTestInput, run_single_config_test)
      loader_test_utils.py   # serialization + document comparison utilities
```

**Input JSON format** (`input/<name>.json`):
```json
{
  "tags": ["loader:text", "feature:chunking"],
  "file_path": "../files/<name>.txt",
  "configs": [
    {},
    {"max_tokens": 256},
    {"max_tokens": 1024}
  ]
}
```
- `tags` — file-level pytest marks applied to every config in this file (used for `-m` filtering)
- `configs` — list of parameter dicts; each becomes a separate test case

**Shared helpers** (used by all test modules):
- `tests/loader_helpers.py` — `collect_loader_test_params(loader_name)` + `run_loader_assert(...)`
- `tests/conftest.py` — sys.path setup, ReportPortal env mapping, marker registration

**Adding a new test suite** mirrors the document loader pattern exactly:
1. Create `tests/runtime/langchain/<component>/test_<subject>.py` using `collect_loader_test_params` + `run_loader_assert`
2. Create `test_data/<SubjectClass>/files/`, `input/`, `output/`
3. Write input JSON files with `tags` and `configs`
4. Generate baselines (see the **Regenerating Baselines** section below)
5. Register any new marks in `pyproject.toml` under `[tool.pytest.ini_options] markers`

---

## Key Paths

| Path | Purpose |
|------|---------|
| `tests/runtime/langchain/document_loaders/` | Pytest test modules |
| `tests/runtime/langchain/document_loaders/test_data/` | All test assets (inputs, baselines, files) |
| `tests/runtime/langchain/document_loaders/test_data/<LOADER>/input/` | Input JSON definitions (configs + tags) |
| `tests/runtime/langchain/document_loaders/test_data/<LOADER>/output/` | Committed baseline JSON files |
| `tests/runtime/langchain/document_loaders/test_data/<LOADER>/files/` | Actual test data files (.txt, .csv, etc.) |
| `tests/runtime/langchain/document_loaders/test_data/scripts/loader_test_runner.py` | Test execution engine |
| `tests/runtime/langchain/document_loaders/test_data/scripts/loader_test_utils.py` | Serialization & comparison utilities |
| `tests/loader_helpers.py` | `collect_loader_test_params()` and `run_loader_assert()` used by all test modules |
| `tests/conftest.py` | Pytest session setup — sys.path, RP env mapping, marker registration |
| `pyproject.toml` | Pytest config, registered marks |

### Loader name → test file mapping

| Loader | Test file |
|--------|-----------|
| `AlitaTextLoader` | `test_alita_text_loader.py` |
| `AlitaCSVLoader` | `test_alita_csv_loader.py` |
| `AlitaJSONLoader` | `test_alita_json_loader.py` |
| `AlitaMarkdownLoader` | `test_alita_markdown_loader.py` |

---

## Prerequisites

Always activate the project virtualenv first:

```bash
# Windows (bash / Git Bash)
source venv/Scripts/activate

# Windows (PowerShell)
& venv\Scripts\Activate.ps1
```

All `pytest` commands below assume the venv is active and the working directory is the project root (`alita-sdk/`).

---

## Running Tests

### Run all document loader tests

```bash
python -m pytest tests/runtime/langchain/document_loaders/ -v
```

### Run a single loader

```bash
python -m pytest tests/runtime/langchain/document_loaders/test_alita_text_loader.py -v
python -m pytest tests/runtime/langchain/document_loaders/test_alita_csv_loader.py -v
python -m pytest tests/runtime/langchain/document_loaders/test_alita_json_loader.py -v
python -m pytest tests/runtime/langchain/document_loaders/test_alita_markdown_loader.py -v
```

### Run a single test case by name

```bash
# Format: test_loader[<input_name>-config<index>]
python -m pytest tests/runtime/langchain/document_loaders/test_alita_text_loader.py::test_loader[text_simple-config0] -v
```

---

## Filtering by Tag (Impact Analysis)

Each input JSON has a `tags` field. Tags are converted to pytest marks (`:` and `-` become `_`).

### Filter by loader

```bash
python -m pytest tests/runtime/langchain/document_loaders/ -m "loader_text" -v
python -m pytest tests/runtime/langchain/document_loaders/ -m "loader_csv" -v
python -m pytest tests/runtime/langchain/document_loaders/ -m "loader_json" -v
python -m pytest tests/runtime/langchain/document_loaders/ -m "loader_markdown" -v
```

### Filter by feature or content type

```bash
# All chunking tests (max_tokens logic)
python -m pytest tests/runtime/langchain/document_loaders/ -m "feature_chunking" -v

# Large file / performance tests
python -m pytest tests/runtime/langchain/document_loaders/ -m "performance" -v

# All unicode/encoding edge cases
python -m pytest tests/runtime/langchain/document_loaders/ -m "edge_encoding" -v

# Empty input edge cases
python -m pytest tests/runtime/langchain/document_loaders/ -m "content_empty" -v
```

### Combine tags (AND / OR / NOT)

```bash
# CSV + chunking only
python -m pytest tests/runtime/langchain/document_loaders/ -m "loader_csv and feature_chunking" -v

# All loaders, skip slow tests (fast CI run)
python -m pytest tests/runtime/langchain/document_loaders/ -m "not performance" -v

# Markdown loader, large content tests only
python -m pytest tests/runtime/langchain/document_loaders/ -m "loader_markdown and content_large" -v
```

### Full tag reference

| Mark | Triggers when |
|------|--------------|
| `loader_text` | Any change to `AlitaTextLoader` |
| `loader_csv` | Any change to `AlitaCSVLoader` |
| `loader_json` | Any change to `AlitaJSONLoader` |
| `loader_markdown` | Any change to `AlitaMarkdownLoader` |
| `feature_chunking` | Changes to chunking / `max_tokens` logic |
| `content_empty` | Empty input handling |
| `content_simple` | Baseline simple content handling |
| `content_large` | Large file handling |
| `content_unicode` | Unicode / multibyte encoding |
| `content_special_characters` | Special character parsing |
| `content_nested` | Nested data structure parsing |
| `content_array` | Array/list structure parsing |
| `content_headers` | Header-structured content |
| `content_markdown` | Markdown-formatted content |
| `performance` | Large files, slow tests |
| `edge_empty_input` | Empty file guards |
| `edge_encoding` | Encoding detection / normalization |
| `edge_special_chars` | Special character edge cases |
| `edge_markdown_in_txt` | Markdown content in `.txt` files |

---

## Reporting Results to ReportPortal

Results from any pytest run can be uploaded to ReportPortal by adding the `--reportportal` flag. Without this flag the plugin is dormant — no data is sent even if credentials are present.

### 1. Install the reporting dependencies

```bash
pip install -e '.[reporting]'
# installs: pytest-reportportal>=5.3, pytest-dotenv
```

### 2. Configure credentials

Add the following to the project `.env` file (already included in `.env.example`):

```bash
RP_ENDPOINT=https://<your-rp-host>/api/receiver
RP_PROJECT=<project-uuid-or-name>
RP_API_KEY=<rp_api_key_token>
RP_LAUNCH=Alita SDK Loader Tests    # display name for the launch in RP
```

`conftest.py` automatically reads these at session start and injects them as pytest-reportportal ini options:

| Env var | pytest-reportportal ini key |
|---|---|
| `RP_ENDPOINT` | `rp_endpoint` |
| `RP_PROJECT` | `rp_project` |
| `RP_LAUNCH` | `rp_launch` |
| `RP_API_KEY` | `rp_uuid` |

`pyproject.toml` already sets `env_files = [".env"]` so the `.env` file is loaded automatically by the `pytest-dotenv` plugin.

### 3. Run tests with RP reporting

```bash
# Report all document loader tests
python -m pytest tests/runtime/langchain/document_loaders/ --reportportal -v

# Report a single loader
python -m pytest tests/runtime/langchain/document_loaders/test_alita_text_loader.py --reportportal -v

# Report a filtered subset (tags)
python -m pytest tests/runtime/langchain/document_loaders/ -m "loader_csv" --reportportal -v
```

Each run creates a new **Launch** in ReportPortal using the name from `RP_LAUNCH`.

### 4. Run without ReportPortal (local / fast iteration)

Simply omit `--reportportal`:

```bash
python -m pytest tests/runtime/langchain/document_loaders/ -v
```

If the env vars are set but you want to explicitly suppress the plugin:

```bash
python -m pytest tests/runtime/langchain/document_loaders/ -p no:reportportal -v
```

---

## Regenerating Baselines

When a loader's behavior intentionally changes, update the affected baseline files.

### Regenerate baseline for one test case

```bash
# Run the test to see the actual output — it is saved to a tmp dir during the pytest run.
# Then copy the actual output over the baseline:
python -m pytest tests/runtime/langchain/document_loaders/test_alita_text_loader.py::test_loader[text_simple-config0] -v -s
```

The actual output is written to a `tmp_path` directory reported in the failure message. Copy it to the corresponding `output/` baseline file:

```
tests/runtime/langchain/document_loaders/test_data/<LOADER>/output/<input>_config_<N>.json
```

### Bulk regenerate baselines via Python

Run this snippet from the project root (with venv active) to regenerate all baselines for one loader:

```python
import sys
sys.path.insert(0, "tests/runtime/langchain/document_loaders/test_data/scripts")
sys.path.insert(0, "tests")

from pathlib import Path
from loader_test_runner import LoaderTestInput, _load_documents_with_production_config
from loader_test_utils import save_documents

LOADER = "AlitaTextLoader"   # change as needed
BASE = Path("tests/runtime/langchain/document_loaders/test_data")
input_dir = BASE / LOADER / "input"
output_dir = BASE / LOADER / "output"

for json_file in sorted(input_dir.glob("*.json")):
    test_input = LoaderTestInput.from_file(json_file)
    file_path = test_input.resolved_file_path(json_file)
    for i, cfg in enumerate(test_input.configs):
        cfg_clean = {k: v for k, v in cfg.items() if not k.startswith("_")}
        docs = _load_documents_with_production_config(file_path, cfg_clean)
        out = output_dir / f"{json_file.stem}_config_{i}.json"
        save_documents(docs, out)
        print(f"Saved {out} ({len(docs)} docs)")
```

---

## Understanding Test Failures

### Count mismatch (`actual=N expected=M`)

The loader produced a different number of documents than the baseline. Common causes:
- Chunking logic changed (check `max_tokens` handling)
- File content was changed
- Loader's split/merge logic was updated

Run with `-s` to see the full diff output from `compare_documents`.

### Metadata mismatch (`source` path)

The `source` field uses `path_suffix` comparison (actual path must *end with* the expected suffix). If this fails, the file path structure changed or the baseline was generated on a different machine with a different root.

### Similarity mismatch (`page_content`)

Page content comparison uses TF-IDF cosine similarity (threshold = 1.0 = exact match after whitespace normalization). If text content changed, regenerate the baseline.

### Baseline not found

```
Baseline not found: tests/runtime/.../output/xxx_config_0.json
```

The baseline file doesn't exist yet. Regenerate it (see above).

---

## Adding a New Test Case

1. Add a test data file to `test_data/<LOADER>/files/`
2. Create an input JSON in `test_data/<LOADER>/input/<name>.json`:
   ```json
   {
     "tags": ["loader:csv", "content:simple"],
     "file_path": "../files/<name>.csv",
     "configs": [
       {},
       {"max_tokens": 256}
     ]
   }
   ```
3. Generate baselines using the bulk script above
4. Run the test to confirm it passes:
   ```bash
   python -m pytest tests/runtime/langchain/document_loaders/test_alita_csv_loader.py -v
   ```
